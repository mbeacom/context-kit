#!/usr/bin/env python3
"""Tests for collect_usage.py, focused on the per-host arithmetic traps."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import collect_usage


def write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def assistant(
    *,
    request_id: str,
    message_id: str,
    model: str = "claude-sonnet-5",
    inp: int = 10,
    out: int = 5,
    cache_read: int = 0,
    cache_create: int = 0,
) -> dict:
    return {
        "type": "assistant",
        "requestId": request_id,
        "message": {
            "id": message_id,
            "model": model,
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            },
        },
    }


class ClaudeCollectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_totals_sum_each_token_class_separately(self) -> None:
        write_jsonl(
            self.root / "proj" / "a.jsonl",
            [
                assistant(
                    request_id="r1",
                    message_id="m1",
                    inp=10,
                    out=5,
                    cache_read=100,
                    cache_create=20,
                )
            ],
        )
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.requests, 1)
        self.assertEqual(report.totals.input_uncached, 10)
        self.assertEqual(report.totals.cache_read, 100)
        self.assertEqual(report.totals.cache_write, 20)
        self.assertEqual(report.totals.output, 5)
        self.assertEqual(report.totals.total_tokens, 135)

    def test_duplicate_responses_are_counted_once(self) -> None:
        # The same response replayed into a subagent transcript must not be
        # billed twice; this is the largest single source of inflated totals.
        entry = assistant(request_id="r1", message_id="m1", inp=10, out=5)
        write_jsonl(self.root / "proj" / "a.jsonl", [entry, entry])
        write_jsonl(self.root / "proj" / "subagents" / "b.jsonl", [entry])
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.requests, 1)
        self.assertEqual(report.duplicates_skipped, 2)
        self.assertEqual(report.totals.output, 5)

    def test_distinct_messages_in_one_request_are_both_counted(self) -> None:
        write_jsonl(
            self.root / "proj" / "a.jsonl",
            [
                assistant(request_id="r1", message_id="m1", out=5),
                assistant(request_id="r1", message_id="m2", out=7),
            ],
        )
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.requests, 2)
        self.assertEqual(report.totals.output, 12)

    def test_records_without_identifiers_are_kept_and_disclosed(self) -> None:
        entry = assistant(request_id="", message_id="", out=5)
        del entry["requestId"]
        del entry["message"]["id"]
        write_jsonl(self.root / "proj" / "a.jsonl", [entry, entry])
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.requests, 2)
        self.assertTrue(any("could not be deduplicated" in n for n in report.notes))

    def test_malformed_and_non_usage_lines_are_skipped(self) -> None:
        path = self.root / "proj" / "a.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "\n".join(
                [
                    "not json at all",
                    json.dumps({"type": "user", "message": {"content": "hi"}}),
                    json.dumps({"type": "attachment"}),
                    json.dumps(assistant(request_id="r1", message_id="m1", out=5)),
                    '{"truncated": ',
                ]
            ),
            encoding="utf-8",
        )
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.requests, 1)

    def test_missing_directory_reports_absence_not_zero_usage(self) -> None:
        report = collect_usage.collect_claude(self.root / "nope")
        self.assertEqual(report.totals.requests, 0)
        self.assertTrue(any("not as zero usage" in n for n in report.notes))

    def test_by_model_buckets_are_separate(self) -> None:
        write_jsonl(
            self.root / "proj" / "a.jsonl",
            [
                assistant(request_id="r1", message_id="m1", model="opus", out=10),
                assistant(request_id="r2", message_id="m2", model="haiku", out=1),
            ],
        )
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.by_model["opus"].output, 10)
        self.assertEqual(report.by_model["haiku"].output, 1)


def build_copilot_db(path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE assistant_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            total_nano_aiu INTEGER,
            token_details_json TEXT
        )"""
    )
    for row in rows:
        conn.execute(
            "INSERT INTO assistant_usage_events (model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, reasoning_tokens, total_nano_aiu, "
            "token_details_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                row.get("model", "claude-opus-5"),
                row.get("input_tokens", 0),
                row.get("output_tokens", 0),
                row.get("cache_read_tokens", 0),
                row.get("cache_write_tokens", 0),
                row.get("reasoning_tokens", 0),
                row.get("total_nano_aiu", 0),
                row.get("token_details_json"),
            ),
        )
    conn.commit()
    conn.close()


class CopilotCollectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.db = self.root / "session-store.db"

    def test_uncached_input_comes_from_token_details_when_present(self) -> None:
        details = json.dumps(
            [
                {"tokenType": "input", "tokenCount": 419},
                {"tokenType": "cache_read", "tokenCount": 165500},
                {"tokenType": "cache_write", "tokenCount": 2268},
                {"tokenType": "output", "tokenCount": 2285},
            ]
        )
        build_copilot_db(
            self.db,
            [
                {
                    # input_tokens is inclusive of cache traffic on this host.
                    "input_tokens": 168187,
                    "output_tokens": 2285,
                    "cache_read_tokens": 165500,
                    "cache_write_tokens": 2268,
                    "total_nano_aiu": 12262000000,
                    "token_details_json": details,
                }
            ],
        )
        report = collect_usage.collect_copilot(self.db)
        self.assertEqual(report.totals.input_uncached, 419)
        self.assertEqual(report.totals.cache_read, 165500)
        self.assertNotEqual(report.totals.input_uncached, 168187)

    def test_uncached_input_is_derived_when_details_missing(self) -> None:
        build_copilot_db(
            self.db,
            [
                {
                    "input_tokens": 1000,
                    "cache_read_tokens": 800,
                    "cache_write_tokens": 150,
                    "output_tokens": 10,
                }
            ],
        )
        report = collect_usage.collect_copilot(self.db)
        self.assertEqual(report.totals.input_uncached, 50)
        self.assertTrue(any("derived by subtracting" in n for n in report.notes))

    def test_derived_uncached_input_never_goes_negative(self) -> None:
        build_copilot_db(
            self.db,
            [{"input_tokens": 100, "cache_read_tokens": 200, "cache_write_tokens": 50}],
        )
        report = collect_usage.collect_copilot(self.db)
        self.assertEqual(report.totals.input_uncached, 0)

    def test_null_cost_is_not_reported_as_a_zero_charge(self) -> None:
        # The column is nullable; treating NULL as recorded would present
        # 0 AIU as an exact host-recorded charge.
        build_copilot_db(self.db, [{"input_tokens": 100, "total_nano_aiu": None}])
        report = collect_usage.collect_copilot(self.db)
        self.assertFalse(report.totals.cost_recorded)
        self.assertIsNone(report.totals.as_dict()["cost_aiu"])
        self.assertTrue(any("recorded no cost" in n for n in report.notes))

    def test_partial_cost_coverage_is_disclosed(self) -> None:
        build_copilot_db(
            self.db,
            [
                {"input_tokens": 10, "total_nano_aiu": 2_000_000_000},
                {"input_tokens": 10, "total_nano_aiu": None},
            ],
        )
        report = collect_usage.collect_copilot(self.db)
        self.assertTrue(report.totals.cost_recorded)
        self.assertAlmostEqual(report.totals.as_dict()["cost_aiu"], 2.0)
        self.assertTrue(any("partial total" in n for n in report.notes))

    def test_recorded_cost_is_reported_in_aiu(self) -> None:
        build_copilot_db(
            self.db, [{"total_nano_aiu": 2_500_000_000, "input_tokens": 10}]
        )
        report = collect_usage.collect_copilot(self.db)
        self.assertTrue(report.totals.cost_recorded)
        self.assertAlmostEqual(report.totals.as_dict()["cost_aiu"], 2.5)

    def test_missing_database_reports_absence(self) -> None:
        report = collect_usage.collect_copilot(self.root / "absent.db")
        self.assertEqual(report.totals.requests, 0)
        self.assertTrue(any("not as zero usage" in n for n in report.notes))

    def test_database_without_usage_table_raises(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.commit()
        conn.close()
        with self.assertRaises(collect_usage.CollectError):
            collect_usage.collect_copilot(self.db)

    def test_cache_hit_ratio_is_share_of_input_side_tokens(self) -> None:
        build_copilot_db(
            self.db,
            [
                {
                    "input_tokens": 100,
                    "cache_read_tokens": 90,
                    "cache_write_tokens": 0,
                    "output_tokens": 1000,
                }
            ],
        )
        report = collect_usage.collect_copilot(self.db)
        # Output must not dilute the ratio; it is not input-side traffic.
        self.assertAlmostEqual(report.totals.as_dict()["cache_hit_ratio"], 0.9)


class ResilienceTest(unittest.TestCase):
    """Failure modes must not be reported as an absence of usage."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_unreadable_transcript_does_not_discard_the_rest(self) -> None:
        write_jsonl(
            self.root / "proj" / "good.jsonl",
            [assistant(request_id="r1", message_id="m1", out=5)],
        )
        locked = self.root / "proj" / "locked.jsonl"
        locked.write_text("{}\n", encoding="utf-8")
        locked.chmod(0o000)
        self.addCleanup(locked.chmod, 0o600)
        if os.access(locked, os.R_OK):  # pragma: no cover - running as root
            self.skipTest("cannot make a file unreadable as this user")

        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.totals.output, 5)
        self.assertTrue(any("could not be read" in n for n in report.notes))

    def test_corrupt_database_raises_rather_than_reporting_no_usage(self) -> None:
        db = self.root / "session-store.db"
        build_copilot_db(db, [{"input_tokens": 10, "output_tokens": 1}] * 200)
        # Damage a data page past the header so the failure surfaces while rows
        # are being fetched, not when the statement is prepared.
        raw = bytearray(db.read_bytes())
        for i in range(2048, min(len(raw), 6144)):
            raw[i] ^= 0xFF
        db.write_bytes(bytes(raw))

        with self.assertRaises(collect_usage.CollectError):
            collect_usage.collect_copilot(db)

    def test_path_containing_a_fragment_character_stays_read_only(self) -> None:
        # An unescaped `#` truncates the URI, dropping mode=ro and creating a
        # new file — which would break the read-only guarantee outright.
        db = self.root / "store#1.db"
        build_copilot_db(db, [{"input_tokens": 10, "output_tokens": 2}])
        before = set(p.name for p in self.root.iterdir())

        report = collect_usage.collect_copilot(db)

        self.assertEqual(report.totals.requests, 1)
        self.assertEqual(set(p.name for p in self.root.iterdir()), before)


class SchemaDriftTest(unittest.TestCase):
    """A host format change must be visible, not silently reported as zero."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_unrecognized_usage_keys_downgrade_counting_and_are_disclosed(self) -> None:
        entry = {
            "type": "assistant",
            "requestId": "r1",
            "message": {
                "id": "m1",
                "model": "m",
                # Plausible future rename; none of the known fields present.
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        }
        write_jsonl(self.root / "proj" / "a.jsonl", [entry])
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.counting, "unknown")
        self.assertTrue(any("may have changed" in n for n in report.notes))

    def test_partial_drift_keeps_counting_exact(self) -> None:
        write_jsonl(
            self.root / "proj" / "a.jsonl",
            [
                assistant(request_id="r1", message_id="m1", out=5),
                {
                    "type": "assistant",
                    "requestId": "r2",
                    "message": {"id": "m2", "model": "m", "usage": {"weird": 1}},
                },
            ],
        )
        report = collect_usage.collect_claude(self.root)
        self.assertEqual(report.counting, "exact")
        self.assertTrue(any("may have changed" in n for n in report.notes))


class SourcePathTest(unittest.TestCase):
    """A report is written to be shared, so it should not carry a home path."""

    def test_source_is_home_relative_by_default(self) -> None:
        report = collect_usage.collect_claude(Path.home() / ".claude" / "projects")
        self.assertFalse(report.source.startswith(str(Path.home())))
        self.assertTrue(report.source.startswith("~/"))

    def test_raw_paths_opt_in_restores_the_absolute_path(self) -> None:
        target = Path.home() / ".claude" / "projects"
        report = collect_usage.collect_claude(target, raw_paths=True)
        self.assertEqual(report.source, str(target))

    def test_path_outside_home_is_left_alone(self) -> None:
        report = collect_usage.collect_claude(Path("/tmp/ck-not-under-home"))
        self.assertEqual(report.source, "/tmp/ck-not-under-home")


class GradeTest(unittest.TestCase):
    def test_reports_declare_counting_and_attribution_grades(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = collect_usage.collect_claude(Path(tmp))
        self.assertEqual(report.counting, "exact")
        # Telemetry can never establish that a tool caused a change.
        self.assertEqual(report.attribution, "observational")


if __name__ == "__main__":
    unittest.main()
