from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "aggregate-findings.py"
SPEC = importlib.util.spec_from_file_location("aggregate_findings", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
aggregate_findings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aggregate_findings)

PLAN_SCRIPT = Path(__file__).parents[1] / "scripts" / "plan-shards.py"
PLAN_SPEC = importlib.util.spec_from_file_location("plan_shards", PLAN_SCRIPT)
assert PLAN_SPEC is not None and PLAN_SPEC.loader is not None
plan_shards = importlib.util.module_from_spec(PLAN_SPEC)
PLAN_SPEC.loader.exec_module(plan_shards)


def digest_of(inv: dict) -> str:
    return aggregate_findings.inventory_digest(inv)


def unit(index: int, size: int = 10, in_scope: bool = True) -> dict:
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
        "schema": aggregate_findings.INVENTORY_SCHEMA,
        "scope": {"include": ["**/*"], "exclude": []},
        "units": units,
    }


def shard_plan(shards: list[dict], inventory_sha256: str | None = None) -> dict:
    return {
        "schema": aggregate_findings.SHARDS_SCHEMA,
        "inventory_sha256": inventory_sha256,
        "shards": shards,
    }


def shard(shard_id: str, units: list[dict], digest: str | None = None) -> dict:
    members = [
        {
            "id": item["id"],
            "path": item["path"],
            "sha256": item["sha256"],
            "bytes": item["bytes"],
            "inspectable": item["inspectable"],
            "range": None,
        }
        for item in units
    ]
    computed = hashlib.sha256(
        "\n".join(member["sha256"] for member in members).encode()
    ).hexdigest()
    return {
        "id": shard_id,
        "digest": digest or computed,
        "bytes": sum(member["bytes"] for member in members),
        "oversized": False,
        "units": members,
    }


def findings_file(
    directory: Path,
    shard_entry: dict,
    reviewed: list[str] | None = None,
    partial: list[dict] | None = None,
    uninspectable: list[dict] | None = None,
    findings: str = "None.",
    digest: str | None = None,
    schema: str = aggregate_findings.FINDINGS_SCHEMA,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = f"""---
schema: {schema}
shard: {shard_entry["id"]}
digest: {digest or shard_entry["digest"]}
units_reviewed: {json.dumps(reviewed or [])}
units_partial: {json.dumps(partial or [])}
units_uninspectable: {json.dumps(uninspectable or [])}
---

## Summary

Reviewed.

## Findings

{findings}

## Gaps observed

- None.

## Coverage

Stated.
"""
    (directory / f"{shard_entry['id']}.md").write_text(body, encoding="utf-8")


class InventoryDigestContractTests(unittest.TestCase):
    """The two scripts must agree; nothing else links their copies.

    A drift is fail-safe at runtime — every aggregation would refuse with
    "shard plan was built from a different inventory" — but it points the user
    at their inventory instead of at the code, so pin it here.
    """

    def test_both_scripts_agree_on_the_digest(self) -> None:
        inv = inventory([unit(1), unit(2, in_scope=False)])

        self.assertEqual(
            plan_shards.inventory_digest(inv),
            aggregate_findings.inventory_digest(inv),
        )

    def test_digest_construction_is_pinned(self) -> None:
        inv = {
            "schema": aggregate_findings.INVENTORY_SCHEMA,
            "generated_at": "ignored",
            "root": "/ignored",
            "scope": {"include": ["**/*.md"], "exclude": []},
            "units": [unit(1)],
        }
        expected = "ac3a1ec6483cfa9807e08c7888a5aae5f98cef61df45dd45cc04335efdf4515b"

        self.assertEqual(expected, aggregate_findings.inventory_digest(inv))
        self.assertEqual(expected, plan_shards.inventory_digest(inv))


class FrontmatterTests(unittest.TestCase):
    def test_parses_json_values(self) -> None:
        fields, body = aggregate_findings.parse_frontmatter(
            '---\nshard: s001\nunits_reviewed: ["u0001"]\n---\n\n# Body\n'
        )

        self.assertIsNotNone(fields)
        assert fields is not None
        self.assertEqual("s001", fields["shard"])
        self.assertEqual(["u0001"], fields["units_reviewed"])
        self.assertIn("# Body", body)

    def test_missing_frontmatter_returns_none(self) -> None:
        fields, body = aggregate_findings.parse_frontmatter("# Body only\n")

        self.assertIsNone(fields)
        self.assertEqual("# Body only\n", body)

    def test_unterminated_frontmatter_returns_none(self) -> None:
        fields, _ = aggregate_findings.parse_frontmatter("---\nshard: s001\n")

        self.assertIsNone(fields)


class FindingParsingTests(unittest.TestCase):
    def test_parses_tags_significance_and_citation(self) -> None:
        parsed, unparsed = aggregate_findings.parse_findings_section(
            ["- [ROTATION, RISK] [significance: high] `docs/a.md:12`", "  detail"]
        )

        self.assertEqual(0, unparsed)
        self.assertEqual("ROTATION,RISK", parsed[0]["tags"])
        self.assertEqual("high", parsed[0]["significance"])
        self.assertEqual("docs/a.md:12", parsed[0]["citation"])

    def test_reports_rather_than_drops_unparsed_bullets(self) -> None:
        parsed, unparsed = aggregate_findings.parse_findings_section(
            ["- [ROTATION] missing the significance marker"]
        )

        self.assertEqual([], parsed)
        self.assertEqual(1, unparsed)

    def test_ignores_prose_bullets(self) -> None:
        parsed, unparsed = aggregate_findings.parse_findings_section(
            ["- a plain note", "None."]
        )

        self.assertEqual(([], 0), (parsed, unparsed))


class AggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.findings_dir = Path(self._tmp.name) / "findings"
        self.addCleanup(self._tmp.cleanup)

    def run_aggregate(self, inv: dict, plan: dict, expected=None) -> tuple:
        plan = dict(plan, inventory_sha256=digest_of(inv))
        return aggregate_findings.aggregate(
            inv, digest_of(inv), plan, self.findings_dir, expected
        )

    def test_complete_run_reports_full_coverage(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(self.findings_dir, entry, reviewed=["u0001", "u0002"])

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertTrue(ledger["complete"])
        self.assertEqual(2, ledger["dispositions"]["reviewed"])
        self.assertEqual(1.0, ledger["coverage"]["units"])
        self.assertEqual([], warnings)

    def test_missing_findings_file_leaves_units_pending(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertFalse(ledger["complete"])
        self.assertEqual(1, ledger["dispositions"]["pending"])
        self.assertEqual(1, ledger["shards"]["pending"])

    def test_unclaimed_unit_stays_pending_and_warns(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(self.findings_dir, entry, reviewed=["u0001"])

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["pending"])
        self.assertFalse(ledger["complete"])
        self.assertTrue(any("never accounted for" in text for text in warnings))

    def test_stale_digest_is_not_merged(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(self.findings_dir, entry, reviewed=["u0001"], digest="f" * 64)

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["shards"]["stale_digest"])
        self.assertEqual(1, ledger["dispositions"]["pending"])
        self.assertFalse(ledger["complete"])
        self.assertTrue(any("corpus changed" in text for text in warnings))

    def test_malformed_findings_file_fails_its_units(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        self.findings_dir.mkdir(parents=True, exist_ok=True)
        (self.findings_dir / "s001.md").write_text("no frontmatter\n", encoding="utf-8")

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["failed"])
        self.assertTrue(any("malformed" in text for text in warnings))

    def test_foreign_findings_schema_is_rejected(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir, entry, reviewed=["u0001"], schema="other/schema"
        )

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["failed"])

    def test_claim_outside_the_shard_is_rejected(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", [units[0]])
        findings_file(self.findings_dir, entry, reviewed=["u0001", "u0002"])

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["reviewed"])
        self.assertEqual(1, ledger["dispositions"]["pending"])
        self.assertTrue(
            any("not in its assignment" in text for text in warnings),
            warnings,
        )

    def test_duplicate_claim_fails_the_unit(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            uninspectable=[{"id": "u0001", "reason": "scanned"}],
        )

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["failed"])
        self.assertTrue(any("more than once" in text for text in warnings))

    def test_out_of_scope_units_leave_the_denominator(self) -> None:
        units = [unit(1), unit(2, in_scope=False)]
        entry = shard("s001", [units[0]])
        findings_file(self.findings_dir, entry, reviewed=["u0001"])

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["out_of_scope"])
        self.assertEqual(1.0, ledger["coverage"]["units"])
        self.assertTrue(ledger["complete"])

    def test_partial_units_are_counted_separately_from_reviewed(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            partial=[{"id": "u0002", "reason": "last 40 pages are image-only"}],
        )

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(1, ledger["dispositions"]["partial"])
        self.assertEqual(1, ledger["dispositions"]["reviewed"])
        self.assertEqual(0.5, ledger["coverage"]["units"])

    def test_zero_in_scope_units_warns_instead_of_reporting_coverage(self) -> None:
        units = [unit(1, in_scope=False), unit(2, in_scope=False)]

        ledger, _, warnings = self.run_aggregate(inventory(units), shard_plan([]))

        self.assertEqual(2, ledger["dispositions"]["out_of_scope"])
        self.assertEqual(0.0, ledger["coverage"]["units"])
        self.assertFalse(
            ledger["complete"], "a run that read nothing is not a finished review"
        )
        self.assertTrue(any("no in-scope units" in text for text in warnings))

    def test_uninspectable_units_do_not_block_completion(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            uninspectable=[{"id": "u0002", "reason": "image-only"}],
        )

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertTrue(ledger["complete"])
        self.assertEqual(0.5, ledger["coverage"]["units"])
        self.assertEqual("image-only", ledger["uninspectable"][0]["reason"])

    def test_byte_coverage_exposes_a_skipped_large_unit(self) -> None:
        units = [unit(1, size=10), unit(2, size=990)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            uninspectable=[{"id": "u0002", "reason": "archive"}],
        )

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(0.5, ledger["coverage"]["units"])
        self.assertEqual(0.01, ledger["coverage"]["bytes"])

    def test_mismatched_inventory_hash_is_refused(self) -> None:
        units = [unit(1)]
        plan = shard_plan([shard("s001", units)], inventory_sha256="b" * 64)

        with self.assertRaises(ValueError):
            aggregate_findings.aggregate(
                inventory(units),
                digest_of(inventory(units)),
                plan,
                self.findings_dir,
                None,
            )

    def test_findings_index_groups_by_tag_and_significance(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            findings=(
                "- [ROTATION] [significance: high] `docs/0001.md:3`\n"
                "- [RISK] [significance: low] `docs/0001.md:9`"
            ),
        )

        _, index, _ = self.run_aggregate(inventory(units), shard_plan([entry]))

        self.assertEqual(2, index["totals"]["findings"])
        self.assertEqual({"RISK": 1, "ROTATION": 1}, index["totals"]["by_tag"])
        self.assertEqual({"high": 1, "low": 1}, index["totals"]["by_significance"])


class AbsenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.findings_dir = Path(self._tmp.name) / "findings"
        self.addCleanup(self._tmp.cleanup)

    def run_aggregate(self, inv, plan, expected):
        plan = dict(plan, inventory_sha256=digest_of(inv))
        return aggregate_findings.aggregate(
            inv, digest_of(inv), plan, self.findings_dir, expected
        )

    def test_absence_is_unavailable_without_an_expected_inventory(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(self.findings_dir, entry, reviewed=["u0001"])

        ledger, _, _ = self.run_aggregate(inventory(units), shard_plan([entry]), None)

        self.assertFalse(ledger["absence"]["available"])
        self.assertEqual([], ledger["absence"]["not_found"])

    def test_full_coverage_yields_not_found(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(self.findings_dir, entry, reviewed=["u0001"])

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([entry]), ["incident report"]
        )

        self.assertEqual(["incident report"], ledger["absence"]["not_found"])
        self.assertEqual([], ledger["absence"]["indeterminate"])

    def test_an_uninspectable_unit_downgrades_not_found_to_indeterminate(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            uninspectable=[{"id": "u0002", "reason": "image-only"}],
        )

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([entry]), ["incident report"]
        )

        self.assertEqual([], ledger["absence"]["not_found"])
        self.assertEqual(
            "incident report", ledger["absence"]["indeterminate"][0]["item"]
        )
        self.assertIn("uninspectable", ledger["absence"]["indeterminate"][0]["reason"])

    def test_a_pending_shard_downgrades_not_found_to_indeterminate(self) -> None:
        units = [unit(1), unit(2)]
        first = shard("s001", [units[0]])
        second = shard("s002", [units[1]])
        findings_file(self.findings_dir, first, reviewed=["u0001"])

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([first, second]), ["incident report"]
        )

        self.assertEqual([], ledger["absence"]["not_found"])
        self.assertIn("pending", ledger["absence"]["indeterminate"][0]["reason"])

    def test_a_partial_unit_downgrades_not_found_to_indeterminate(self) -> None:
        units = [unit(1), unit(2)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            partial=[{"id": "u0002", "reason": "tail of the file is unreadable"}],
        )

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([entry]), ["incident report"]
        )

        self.assertEqual([], ledger["absence"]["not_found"])
        self.assertIn("partial", ledger["absence"]["indeterminate"][0]["reason"])

    def test_absence_is_unavailable_when_nothing_was_in_scope(self) -> None:
        units = [unit(1, in_scope=False)]

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([]), ["incident report"]
        )

        self.assertFalse(ledger["absence"]["available"])
        self.assertEqual([], ledger["absence"]["not_found"])
        self.assertIn("no in-scope units", ledger["absence"]["reason"])

    def test_a_mentioned_item_is_neither_absent_nor_indeterminate(self) -> None:
        units = [unit(1)]
        entry = shard("s001", units)
        findings_file(
            self.findings_dir,
            entry,
            reviewed=["u0001"],
            findings="- [DOC] [significance: low] `docs/0001.md:1` incident report",
        )

        ledger, _, _ = self.run_aggregate(
            inventory(units), shard_plan([entry]), ["incident report"]
        )

        self.assertEqual([], ledger["absence"]["not_found"])
        self.assertEqual([], ledger["absence"]["indeterminate"])


class RenderTests(unittest.TestCase):
    def test_coverage_markdown_states_the_denominator_and_verdicts(self) -> None:
        ledger = {
            "complete": False,
            "dispositions": {
                "reviewed": 3,
                "partial": 0,
                "uninspectable": 1,
                "out_of_scope": 1,
                "failed": 0,
                "pending": 2,
            },
            "coverage": {"units": 0.5, "bytes": 0.566},
            "shards": {
                "total": 3,
                "complete": 2,
                "failed": 0,
                "pending": 1,
                "stale_digest": 0,
            },
            "uninspectable": [{"id": "u1", "path": "docs/blob.md", "reason": "binary"}],
            "absence": {
                "available": True,
                "not_found": [],
                "indeterminate": [{"item": "incident report", "reason": "2 pending"}],
            },
            "warnings": ["shard s003: something"],
        }

        text = aggregate_findings.render_coverage_markdown(ledger)

        self.assertIn("Complete: **no**", text)
        self.assertIn("Unit coverage: 50.0%", text)
        self.assertIn("Byte coverage: 56.6%", text)
        self.assertIn("incident report — 2 pending", text)
        self.assertIn("docs/blob.md", text)

    def test_findings_markdown_warns_when_the_run_is_incomplete(self) -> None:
        text = aggregate_findings.render_findings_markdown(
            {
                "complete": False,
                "coverage": {"units": 0.5, "bytes": 0.5},
                "warnings": [],
                "totals": {"findings": 0, "by_tag": {}, "by_significance": {}},
                "findings": [],
            }
        )

        self.assertIn("the run is not complete", text)
        self.assertIn("50.0% of in-scope units", text)

    def test_findings_markdown_qualifies_a_complete_but_thin_run(self) -> None:
        """`complete` alone is not enough: partial/uninspectable units keep a
        run complete while most of the corpus went unread."""
        text = aggregate_findings.render_findings_markdown(
            {
                "complete": True,
                "coverage": {"units": 0.01, "bytes": 0.001},
                "warnings": [],
                "totals": {"findings": 3, "by_tag": {}, "by_significance": {}},
                "findings": [],
            }
        )

        self.assertIn("coverage ledger", text)
        self.assertIn("1.0% of in-scope units", text)

    def test_findings_markdown_surfaces_ledger_warnings(self) -> None:
        text = aggregate_findings.render_findings_markdown(
            {
                "complete": True,
                "coverage": {"units": 1.0, "bytes": 1.0},
                "warnings": ["no in-scope units: the scope rules matched nothing"],
                "totals": {"findings": 0, "by_tag": {}, "by_significance": {}},
                "findings": [],
            }
        )

        self.assertIn("1 warning(s)", text)

    def test_findings_markdown_stays_clean_on_a_full_run(self) -> None:
        text = aggregate_findings.render_findings_markdown(
            {
                "complete": True,
                "coverage": {"units": 1.0, "bytes": 1.0},
                "warnings": [],
                "totals": {"findings": 2, "by_tag": {}, "by_significance": {}},
                "findings": [],
            }
        )

        self.assertNotIn("coverage ledger", text)


class CliTests(unittest.TestCase):
    def test_incomplete_run_exits_nonzero_unless_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            units = [unit(1)]
            inventory_path = base / "inventory.json"
            inventory_path.write_text(json.dumps(inventory(units)), encoding="utf-8")
            digest = digest_of(inventory(units))
            plan_path = base / "shards.json"
            plan_path.write_text(
                json.dumps(shard_plan([shard("s001", units)], digest)), encoding="utf-8"
            )
            argv = [
                "--inventory",
                str(inventory_path),
                "--shards",
                str(plan_path),
                "--findings-dir",
                str(base / "findings"),
                "--out-dir",
                str(base / "report"),
            ]

            self.assertEqual(1, aggregate_findings.main(argv))
            self.assertEqual(0, aggregate_findings.main([*argv, "--allow-incomplete"]))
            self.assertTrue((base / "report" / "coverage.json").is_file())
            self.assertTrue((base / "report" / "findings.md").is_file())

    def test_reinventorying_an_unchanged_corpus_does_not_invalidate_the_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            units = [unit(1)]
            entry = shard("s001", units)
            findings_file(base / "findings", entry, reviewed=["u0001"])
            plan_path = base / "shards.json"
            plan_path.write_text(
                json.dumps(shard_plan([entry], digest_of(inventory(units)))),
                encoding="utf-8",
            )
            inventory_path = base / "inventory.json"
            argv = [
                "--inventory",
                str(inventory_path),
                "--shards",
                str(plan_path),
                "--findings-dir",
                str(base / "findings"),
                "--out-dir",
                str(base / "report"),
            ]

            for stamp in ("2026-01-01T00:00:00+00:00", "2099-12-31T23:59:59+00:00"):
                regenerated = dict(inventory(units), generated_at=stamp)
                inventory_path.write_text(json.dumps(regenerated), encoding="utf-8")
                self.assertEqual(0, aggregate_findings.main(argv))


if __name__ == "__main__":
    unittest.main()
