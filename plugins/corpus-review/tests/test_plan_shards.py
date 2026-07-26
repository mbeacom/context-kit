from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "plan-shards.py"
SPEC = importlib.util.spec_from_file_location("plan_shards", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
plan_shards = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan_shards)


def unit(index: int, size: int, in_scope: bool = True) -> dict:
    return {
        "id": f"u{index:04d}",
        "path": f"docs/{index:04d}.md",
        "bytes": size,
        "sha256": f"{index:064d}",
        "inspectable": "text",
        "in_scope": in_scope,
        "range": None,
    }


def inventory(units: list[dict]) -> dict:
    return {
        "schema": plan_shards.INVENTORY_SCHEMA,
        "generated_at": "2026-07-25T00:00:00+00:00",
        "root": "/corpus",
        "scope": {"include": ["**/*"], "exclude": []},
        "totals": {},
        "units": units,
    }


class PackTests(unittest.TestCase):
    def test_respects_the_byte_budget(self) -> None:
        batches = plan_shards.pack([unit(i, 40) for i in range(1, 6)], 100, 99)

        self.assertEqual([2, 2, 1], [len(batch) for batch in batches])

    def test_respects_the_unit_ceiling(self) -> None:
        batches = plan_shards.pack([unit(i, 1) for i in range(1, 8)], 10_000, 3)

        self.assertEqual([3, 3, 1], [len(batch) for batch in batches])

    def test_oversized_unit_gets_its_own_shard(self) -> None:
        units = [unit(1, 10), unit(2, 5_000), unit(3, 10)]

        batches = plan_shards.pack(units, 100, 10)

        self.assertEqual(
            [["u0001"], ["u0002"], ["u0003"]],
            [[item["id"] for item in batch] for batch in batches],
        )

    def test_inventory_order_is_never_rearranged(self) -> None:
        units = [unit(1, 90), unit(2, 10), unit(3, 90)]

        batches = plan_shards.pack(units, 100, 10)

        self.assertEqual(
            [["u0001", "u0002"], ["u0003"]],
            [[item["id"] for item in batch] for batch in batches],
        )


class DigestTests(unittest.TestCase):
    def test_digest_construction_is_pinned(self) -> None:
        """Pin the construction so a silent change invalidates saved findings.

        The digest is the resumption key: if it changes shape, every existing
        findings file stops matching and reviews silently restart.
        """
        members = [unit(1, 10), unit(2, 10)]

        self.assertEqual(
            "c0165699c6e9472c8bc68318b042b1a8b5e646ffc9e3d928e9b2d003cade2611",
            plan_shards.shard_digest(members),
        )

    def test_digest_changes_when_content_changes(self) -> None:
        before = [unit(1, 10)]
        after = [dict(before[0], sha256="deadbeef")]

        self.assertNotEqual(
            plan_shards.shard_digest(before), plan_shards.shard_digest(after)
        )

    def test_digest_changes_when_membership_order_changes(self) -> None:
        members = [unit(1, 10), unit(2, 10)]

        self.assertNotEqual(
            plan_shards.shard_digest(members),
            plan_shards.shard_digest(list(reversed(members))),
        )


class BuildPlanTests(unittest.TestCase):
    def test_out_of_scope_units_are_never_sharded(self) -> None:
        data = inventory([unit(1, 10), unit(2, 10, in_scope=False)])

        plan = plan_shards.build_plan(data, "abc", 1_000, 10)

        assigned = [item["id"] for shard in plan["shards"] for item in shard["units"]]
        self.assertEqual(["u0001"], assigned)
        self.assertEqual(1, plan["totals"]["units"])

    def test_plan_binds_to_the_inventory_hash(self) -> None:
        plan = plan_shards.build_plan(inventory([unit(1, 10)]), "abc123", 100, 10)

        self.assertEqual("abc123", plan["inventory_sha256"])
        self.assertEqual(plan_shards.SCHEMA, plan["schema"])

    def test_oversized_shards_are_flagged_in_totals(self) -> None:
        plan = plan_shards.build_plan(inventory([unit(1, 5_000)]), "abc", 100, 10)

        self.assertEqual(1, plan["totals"]["oversized"])
        self.assertTrue(plan["shards"][0]["oversized"])

    def test_shard_members_carry_original_location(self) -> None:
        plan = plan_shards.build_plan(inventory([unit(1, 10)]), "abc", 100, 10)
        member = plan["shards"][0]["units"][0]

        self.assertEqual("docs/0001.md", member["path"])
        self.assertIn("sha256", member)
        self.assertIn("range", member)


class LoadInventoryTests(unittest.TestCase):
    def test_rejects_a_foreign_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps({"schema": "other", "units": []}), "utf-8")

            with self.assertRaises(ValueError):
                plan_shards.load_inventory(path)

    def test_digest_changes_when_units_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps(inventory([unit(1, 10)])), "utf-8")
            _, first = plan_shards.load_inventory(path)

            path.write_text(json.dumps(inventory([unit(1, 11)])), "utf-8")
            _, second = plan_shards.load_inventory(path)

            self.assertNotEqual(first, second)

    def test_digest_ignores_volatile_metadata(self) -> None:
        base = inventory([unit(1, 10)])
        later = dict(base, generated_at="2099-01-01T00:00:00+00:00", root="/moved")

        self.assertEqual(
            plan_shards.inventory_digest(base),
            plan_shards.inventory_digest(later),
            "a re-inventory of an unchanged corpus must not invalidate the plan",
        )

    def test_digest_changes_when_scope_rules_change(self) -> None:
        base = inventory([unit(1, 10)])
        widened = dict(base, scope={"include": ["**/*"], "exclude": ["skip/**"]})

        self.assertNotEqual(
            plan_shards.inventory_digest(base),
            plan_shards.inventory_digest(widened),
        )


class CliTests(unittest.TestCase):
    def test_writes_a_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "inventory.json"
            source.write_text(json.dumps(inventory([unit(1, 10)])), "utf-8")
            out = Path(tmp) / "shards.json"

            code = plan_shards.main(["--inventory", str(source), "--out", str(out)])

            self.assertEqual(0, code)
            self.assertEqual(1, json.loads(out.read_text("utf-8"))["totals"]["shards"])

    def test_rejects_a_nonpositive_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "inventory.json"
            source.write_text(json.dumps(inventory([])), "utf-8")

            code = plan_shards.main(
                [
                    "--inventory",
                    str(source),
                    "--out",
                    str(Path(tmp) / "s.json"),
                    "--max-bytes",
                    "0",
                ]
            )

            self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
