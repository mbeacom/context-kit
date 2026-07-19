from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate-handoff.py"
SPEC = importlib.util.spec_from_file_location("validate_handoff", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validate_handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_handoff)


def valid_artifact() -> bytes:
    sections = "\n\n".join(
        f"## {heading}\n\n- None." for heading in validate_handoff.REQUIRED_SECTIONS
    )
    return f"""---
schema: context-kit/handoff-v1
generated_at: "2026-07-18T23:00:00-04:00"
repository: mbeacom/context-kit
worktree: /tmp/context-kit
branch: feature/context-handoff
head: aaaaaaa
base_ref: main
base_commit: bbbbbbb
worktree_state: dirty
---

# Context Handoff

{sections}
""".encode()


class ValidateDocumentTests(unittest.TestCase):
    def test_accepts_complete_bounded_artifact(self) -> None:
        metadata, errors = validate_handoff.validate_document(valid_artifact())

        self.assertEqual([], errors)
        self.assertEqual("mbeacom/context-kit", metadata["repository"])

    def test_rejects_missing_required_section(self) -> None:
        artifact = valid_artifact().replace(
            b"## Decisions\n\n- None.\n\n",
            b"",
        )

        _metadata, errors = validate_handoff.validate_document(artifact)

        self.assertTrue(any("level-two sections" in error for error in errors))
        self.assertTrue(any("missing required section: Decisions" in error for error in errors))

    def test_rejects_unresolved_template_placeholder(self) -> None:
        artifact = valid_artifact().replace(b"- None.", b"- {{TODO}}", 1)

        _metadata, errors = validate_handoff.validate_document(artifact)

        self.assertIn(
            "artifact contains unresolved {{...}} template placeholders",
            errors,
        )

    def test_rejects_missing_canonical_title(self) -> None:
        artifact = valid_artifact().replace(b"# Context Handoff", b"# Task Notes")

        _metadata, errors = validate_handoff.validate_document(artifact)

        self.assertIn(
            "document must contain exactly one '# Context Handoff' title",
            errors,
        )

    def test_rejects_timestamp_without_timezone(self) -> None:
        artifact = valid_artifact().replace(
            b"2026-07-18T23:00:00-04:00",
            b"2026-07-18T23:00:00",
        )

        _metadata, errors = validate_handoff.validate_document(artifact)

        self.assertIn("generated_at must include a timezone", errors)


class FreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata, errors = validate_handoff.validate_document(valid_artifact())
        self.assertEqual([], errors)

    def test_identity_difference_is_mismatch(self) -> None:
        mismatches, stale = validate_handoff.compare_context(
            self.metadata,
            {"repository": "other/project", "branch": None, "base_ref": None},
        )

        self.assertEqual([], stale)
        self.assertEqual(1, len(mismatches))
        self.assertIn("repository mismatch", mismatches[0])

    def test_head_difference_is_stale(self) -> None:
        mismatches, stale = validate_handoff.compare_context(
            self.metadata,
            {"head": "ccccccc"},
        )

        self.assertEqual([], mismatches)
        self.assertEqual(1, len(stale))
        self.assertIn("head stale", stale[0])

    def test_path_uses_environment_override(self) -> None:
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_HANDOFF_PATH": "state/custom.md"},
            clear=False,
        ):
            path = validate_handoff.resolve_path(None)

        self.assertEqual(Path("state/custom.md"), path)


class MainTests(unittest.TestCase):
    def run_main(self, *arguments: str) -> int:
        with patch("builtins.print"):
            return validate_handoff.main(arguments)

    def test_main_returns_mismatch_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.md"
            path.write_bytes(valid_artifact())

            result = self.run_main(
                str(path),
                "--current-repository",
                "other/project",
            )

        self.assertEqual(2, result)

    def test_main_returns_stale_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.md"
            path.write_bytes(valid_artifact())

            result = self.run_main(str(path), "--current-head", "ccccccc")

        self.assertEqual(3, result)

    def test_main_returns_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.md"
            path.write_text("not a handoff", encoding="utf-8")

            result = self.run_main(str(path))

        self.assertEqual(1, result)


if __name__ == "__main__":
    unittest.main()
