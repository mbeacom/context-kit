from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "inventory-corpus.py"
SPEC = importlib.util.spec_from_file_location("inventory_corpus", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
inventory_corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory_corpus)


class GlobTranslationTests(unittest.TestCase):
    def matches(self, pattern: str, path: str) -> bool:
        return inventory_corpus.translate_glob(pattern).match(path) is not None

    def test_single_star_does_not_cross_separators(self) -> None:
        self.assertTrue(self.matches("docs/*.md", "docs/a.md"))
        self.assertFalse(self.matches("docs/*.md", "docs/nested/a.md"))

    def test_double_star_crosses_separators_and_matches_root(self) -> None:
        self.assertTrue(self.matches("**/*.md", "a.md"))
        self.assertTrue(self.matches("**/*.md", "docs/deep/a.md"))
        self.assertTrue(self.matches("skip/**", "skip/nested/a.md"))

    def test_question_mark_and_character_class(self) -> None:
        self.assertTrue(self.matches("r?.md", "r1.md"))
        self.assertFalse(self.matches("r?.md", "r10.md"))
        self.assertTrue(self.matches("r[0-9].md", "r7.md"))
        self.assertFalse(self.matches("r[!0-9].md", "r7.md"))

    def test_literal_metacharacters_are_escaped(self) -> None:
        self.assertTrue(self.matches("a+b.md", "a+b.md"))
        self.assertFalse(self.matches("a+b.md", "aab.md"))


class ClassificationTests(unittest.TestCase):
    def test_empty_and_text_and_binary(self) -> None:
        self.assertEqual(inventory_corpus.EMPTY, inventory_corpus.classify(b"", 0))
        self.assertEqual(inventory_corpus.TEXT, inventory_corpus.classify(b"hello", 5))
        self.assertEqual(
            inventory_corpus.BINARY, inventory_corpus.classify(b"a\x00b", 3)
        )

    def test_mostly_valid_utf8_is_lossy_not_binary(self) -> None:
        data = ("ok " * 400).encode("utf-8") + b"\xff"
        self.assertEqual(
            inventory_corpus.TEXT_LOSSY, inventory_corpus.classify(data, len(data))
        )

    def test_heavily_invalid_utf8_is_binary(self) -> None:
        data = b"\xff\xfe\xfd\xfc"
        self.assertEqual(
            inventory_corpus.BINARY, inventory_corpus.classify(data, len(data))
        )


class SplitTextUnitTests(unittest.TestCase):
    def test_splits_on_line_boundaries_within_budget(self) -> None:
        data = b"aaaa\nbbbb\ncccc\n"
        chunks = inventory_corpus.split_text_unit(data, 10)

        self.assertEqual([(1, 2, b"aaaa\nbbbb\n"), (3, 3, b"cccc\n")], chunks)

    def test_oversized_single_line_is_not_cut(self) -> None:
        data = b"x" * 50 + b"\n"
        chunks = inventory_corpus.split_text_unit(data, 10)

        self.assertEqual(1, len(chunks))
        self.assertEqual(data, chunks[0][2])

    def test_chunks_reassemble_to_the_original(self) -> None:
        data = b"".join(f"line {index}\n".encode() for index in range(50))
        chunks = inventory_corpus.split_text_unit(data, 32)

        self.assertEqual(data, b"".join(chunk for _, _, chunk in chunks))


class BuildInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "corpus"
        (self.root / "docs").mkdir(parents=True)
        (self.root / "skip").mkdir()
        (self.root / "docs" / "b.md").write_text("beta\n", encoding="utf-8")
        (self.root / "docs" / "a.md").write_text("alpha\n", encoding="utf-8")
        (self.root / "skip" / "ignored.md").write_text("nope\n", encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def build(self, **kwargs: object) -> dict:
        scope = inventory_corpus.Scope(
            kwargs.get("include", ["**/*.md"]),  # type: ignore[arg-type]
            kwargs.get("exclude", ["skip/**"]),  # type: ignore[arg-type]
        )
        return inventory_corpus.build_inventory(
            self.root,
            scope,
            follow_symlinks=bool(kwargs.get("follow_symlinks", False)),
            max_unit_bytes=kwargs.get("max_unit_bytes"),  # type: ignore[arg-type]
        )

    def test_units_are_sorted_and_identifiers_are_stable(self) -> None:
        first = self.build()
        second = self.build()

        paths = [unit["path"] for unit in first["units"]]
        self.assertEqual(sorted(paths), paths)
        self.assertEqual(
            [(unit["id"], unit["path"]) for unit in first["units"]],
            [(unit["id"], unit["path"]) for unit in second["units"]],
        )

    def test_excluded_units_are_listed_but_not_opened(self) -> None:
        inventory = self.build()
        excluded = [unit for unit in inventory["units"] if not unit["in_scope"]]

        self.assertEqual(["skip/ignored.md"], [unit["path"] for unit in excluded])
        self.assertIsNone(excluded[0]["sha256"])
        self.assertIsNone(excluded[0]["inspectable"])
        self.assertEqual(1, inventory["totals"]["out_of_scope_units"])

    def test_scope_rules_are_recorded(self) -> None:
        inventory = self.build()

        self.assertEqual(["**/*.md"], inventory["scope"]["include"])
        self.assertEqual(["skip/**"], inventory["scope"]["exclude"])

    def test_in_scope_units_are_hashed(self) -> None:
        inventory = self.build()
        in_scope = [unit for unit in inventory["units"] if unit["in_scope"]]

        self.assertEqual(2, len(in_scope))
        for unit in in_scope:
            self.assertEqual(64, len(str(unit["sha256"])))
            self.assertEqual(inventory_corpus.TEXT, unit["inspectable"])

    def test_large_text_unit_is_subdivided_with_ranges(self) -> None:
        big = self.root / "docs" / "big.md"
        big.write_text("".join(f"row {index}\n" for index in range(40)), "utf-8")

        inventory = self.build(max_unit_bytes=40)
        parts = [unit for unit in inventory["units"] if unit["path"] == "docs/big.md"]

        self.assertGreater(len(parts), 1)
        self.assertEqual(1, parts[0]["range"]["start"])
        self.assertEqual(
            len({str(unit["sha256"]) for unit in parts}),
            len(parts),
            "each subdivided unit hashes its own content",
        )
        starts = [unit["range"]["start"] for unit in parts]
        self.assertEqual(sorted(starts), starts)

    def test_binary_units_are_never_subdivided(self) -> None:
        (self.root / "docs" / "blob.md").write_bytes(b"\x00" * 500)

        inventory = self.build(max_unit_bytes=40)
        parts = [unit for unit in inventory["units"] if unit["path"] == "docs/blob.md"]

        self.assertEqual(1, len(parts))
        self.assertEqual(inventory_corpus.BINARY, parts[0]["inspectable"])

    def test_symlinks_are_skipped_by_default(self) -> None:
        link = self.root / "docs" / "link.md"
        link.symlink_to(self.root / "docs" / "a.md")

        paths = [unit["path"] for unit in self.build()["units"]]
        self.assertNotIn("docs/link.md", paths)


class OutputGuardTests(unittest.TestCase):
    def test_refuses_to_write_inside_the_corpus_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(ValueError):
                inventory_corpus.resolve_output(root / "work" / "i.json", root)

    def test_allows_a_sibling_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = (Path(tmp) / "corpus").resolve()
            root.mkdir()
            resolved = inventory_corpus.resolve_output(
                Path(tmp) / "work" / "i.json", root
            )
            self.assertTrue(str(resolved).endswith("work/i.json"))


class CliTests(unittest.TestCase):
    def test_writes_inventory_and_reports_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "corpus"
            root.mkdir()
            (root / "a.md").write_text("alpha\n", encoding="utf-8")
            out = Path(tmp) / "work" / "inventory.json"

            code = inventory_corpus.main(
                ["--root", str(root), "--out", str(out), "--include", "**/*.md"]
            )

            self.assertEqual(0, code)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(inventory_corpus.SCHEMA, data["schema"])
            self.assertEqual(1, data["totals"]["in_scope_units"])

    def test_rejects_a_missing_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = inventory_corpus.main(
                [
                    "--root",
                    str(Path(tmp) / "absent"),
                    "--out",
                    str(Path(tmp) / "o.json"),
                ]
            )
            self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
