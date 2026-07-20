from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "memory-provider.py"
SPEC = importlib.util.spec_from_file_location("memory_provider", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
memory_provider = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_provider
SPEC.loader.exec_module(memory_provider)


class MemoryProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "memory"
        self.source = self.root / "source.txt"
        self.source.write_text("verified source\n", encoding="utf-8")
        self.record = self.root / "record.md"
        self.write_record()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_record(
        self,
        *,
        cues: list[str] | None = None,
        source_hash: str | None = None,
        review: str = "accepted",
        freshness: str = "current",
    ):
        cues = ["retry policy", "billing backoff"] if cues is None else cues
        cue_text = "\n".join(f"- {cue}" for cue in cues) if cues else "- None."
        digest = source_hash or hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.record.write_text(
            "\n".join(
                [
                    "---",
                    "schema: context-kit/memory-v1",
                    "id: retry-policy",
                    "type: decision",
                    "scope: project",
                    "repository: mbeacom/context-kit",
                    "branch: main",
                    "head: abcdef0123456789",
                    "observed_at: 2026-07-19T12:00:00-04:00",
                    "captured_at: 2026-07-19T12:05:00-04:00",
                    f"freshness: {freshness}",
                    f"review: {review}",
                    f"source: {self.source}",
                    f"source_hash: {digest}",
                    "---",
                    "",
                    "## Primary Memory",
                    "",
                    "Retry billing requests with bounded exponential backoff.",
                    "",
                    "## Cue Anchors",
                    "",
                    cue_text,
                    "",
                    "## Evidence",
                    "",
                    f"- `{self.source}` — exact reviewed source.",
                    "",
                    "## Supersedes",
                    "",
                    "- None.",
                    "",
                    "## Review Notes",
                    "",
                    "- Accepted after source review.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def invoke(self, argv: list[str], stdin: bytes = b"") -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        fake_stdin = type("FakeStdin", (), {"buffer": io.BytesIO(stdin)})()
        with (
            patch("sys.stdin", fake_stdin),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = memory_provider.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def base_args(self) -> list[str]:
        return ["--home", str(self.home), "--project", "mbeacom/context-kit"]

    def project_slug(self, project: str = "mbeacom/context-kit") -> str:
        return memory_provider.Config(
            provider="none",
            home=self.home,
            project=project,
            auto_capture=False,
        ).project_slug

    def test_validates_memory_contract(self) -> None:
        result, stdout, _ = self.invoke(["validate", str(self.record)])

        self.assertEqual(0, result)
        self.assertEqual("retry-policy", json.loads(stdout)["id"])

    def test_rejects_more_than_three_cues(self) -> None:
        self.write_record(cues=["a", "b", "c", "d"])

        result, _, stderr = self.invoke(["validate", str(self.record)])

        self.assertEqual(2, result)
        self.assertIn("at most 3", stderr)

    def test_rejects_source_hash_drift(self) -> None:
        self.write_record(source_hash="0" * 64)

        result, _, stderr = self.invoke(["validate", str(self.record)])

        self.assertEqual(2, result)
        self.assertIn("does not match", stderr)

    def test_rejects_invalid_project_provenance(self) -> None:
        replacements = (
            ("scope: project", "scope: personal"),
            ("repository: mbeacom/context-kit", "repository: invalid"),
            ("branch: main", "branch: invalid branch"),
            ("branch: main", "branch: foo/.hidden"),
            ("branch: main", "branch: foo/name.lock/bar"),
            ("branch: main", "branch: HEAD"),
            ("head: abcdef0123456789", "head: not-a-commit"),
        )
        for original, replacement in replacements:
            with self.subTest(replacement=replacement):
                self.write_record()
                text = self.record.read_text(encoding="utf-8")
                self.record.write_text(
                    text.replace(original, replacement),
                    encoding="utf-8",
                )

                result, _, _ = self.invoke(["validate", str(self.record)])

                self.assertEqual(2, result)

    def test_rejects_nonbullet_cues_and_empty_required_sections(self) -> None:
        replacements = (
            ("- retry policy\n- billing backoff", "retry policy"),
            ("## Supersedes\n\n- None.", "## Supersedes\n"),
            (
                "## Review Notes\n\n- Accepted after source review.",
                "## Review Notes\n",
            ),
        )
        for original, replacement in replacements:
            with self.subTest(replacement=replacement):
                self.write_record()
                text = self.record.read_text(encoding="utf-8")
                self.record.write_text(
                    text.replace(original, replacement),
                    encoding="utf-8",
                )

                result, _, _ = self.invoke(["validate", str(self.record)])

                self.assertEqual(2, result)

    def test_accepts_level_two_heading_inside_fenced_evidence(self) -> None:
        text = self.record.read_text(encoding="utf-8")
        self.record.write_text(
            text.replace(
                f"- `{self.source}` — exact reviewed source.",
                "\n".join(
                    [
                        f"- `{self.source}` — exact reviewed source.",
                        "```markdown",
                        "## Nested source heading",
                        "```",
                    ]
                ),
            ),
            encoding="utf-8",
        )

        result, _, _ = self.invoke(["validate", str(self.record)])

        self.assertEqual(0, result)

    def test_accepts_nested_fence_inside_longer_fenced_evidence(self) -> None:
        text = self.record.read_text(encoding="utf-8")
        self.record.write_text(
            text.replace(
                f"- `{self.source}` — exact reviewed source.",
                "\n".join(
                    [
                        f"- `{self.source}` — exact reviewed source.",
                        "````markdown",
                        "```markdown",
                        "## Nested source heading",
                        "```",
                        "````",
                    ]
                ),
            ),
            encoding="utf-8",
        )

        result, _, _ = self.invoke(["validate", str(self.record)])

        self.assertEqual(0, result)

    def test_local_capture_is_idempotent(self) -> None:
        argv = ["capture", str(self.record), "--provider", "none", *self.base_args()]

        first, first_stdout, _ = self.invoke(argv)
        second, second_stdout, _ = self.invoke(argv)

        self.assertEqual(0, first)
        self.assertEqual(0, second)
        self.assertEqual("created", json.loads(first_stdout)["status"])
        self.assertEqual("unchanged", json.loads(second_stdout)["status"])
        saved = self.home / "records" / self.project_slug() / "retry-policy.md"
        self.assertEqual(self.record.read_bytes(), saved.read_bytes())

    def test_project_slug_separates_distinct_valid_identifiers(self) -> None:
        identifiers = ("foo/bar-baz", "foo-bar/baz", "Foo/Bar-Baz")
        slugs = [self.project_slug(project) for project in identifiers]

        self.assertEqual(len(identifiers), len(set(slugs)))
        self.assertTrue(all("/" not in slug and len(slug) <= 96 for slug in slugs))
        self.assertEqual(slugs[0], self.project_slug(identifiers[0]))

    def test_write_once_cannot_clobber_a_concurrent_writer(self) -> None:
        destination = self.root / "concurrent" / "record.md"
        barrier = threading.Barrier(2)
        real_link = os.link

        def synchronized_link(source, target):
            barrier.wait(timeout=5)
            return real_link(source, target)

        def publish(raw: bytes) -> str:
            try:
                return memory_provider._write_once(destination, raw)
            except memory_provider.Refusal as exc:
                return str(exc)

        with (
            patch.object(memory_provider.os, "link", side_effect=synchronized_link),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(executor.map(publish, (b"first", b"second")))

        self.assertIn("created", results)
        self.assertTrue(any("refusing to overwrite" in result for result in results))
        self.assertIn(destination.read_bytes(), {b"first", b"second"})

    def test_doctor_reports_ready_local_mode(self) -> None:
        result, stdout, _ = self.invoke(
            ["doctor", "--provider", "none", *self.base_args()]
        )

        self.assertEqual(0, result)
        report = json.loads(stdout)
        self.assertEqual("ready", report["status"])
        self.assertEqual("local", report["mode"])

    def test_doctor_rejects_non_repository_project(self) -> None:
        result, _, stderr = self.invoke(
            [
                "doctor",
                "--provider",
                "none",
                "--home",
                str(self.home),
                "--project",
                "invalid",
            ]
        )

        self.assertEqual(2, result)
        self.assertIn("owner/name", stderr)

    def test_local_search_matches_primary_memory_and_cues(self) -> None:
        capture, _, _ = self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )

        result, stdout, _ = self.invoke(
            ["search", "billing backoff", "--provider", "none", *self.base_args()]
        )

        self.assertEqual(0, capture)
        self.assertEqual(0, result)
        report = json.loads(stdout)
        self.assertEqual("local", report["provider"])
        self.assertEqual("retry-policy", report["records"][0]["id"])

    def test_local_search_returns_drifted_source_as_candidate(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        self.source.write_text("changed evidence\n", encoding="utf-8")

        result, stdout, _ = self.invoke(
            ["search", "billing backoff", "--provider", "none", *self.base_args()]
        )

        self.assertEqual(0, result)
        record = json.loads(stdout)["records"][0]
        self.assertEqual("drifted", record["source_state"])

    def test_state_events_preserve_artifact_and_control_active_recall(self) -> None:
        self.write_record(review="proposed")
        original = self.record.read_bytes()
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )

        inactive, inactive_stdout, _ = self.invoke(
            ["search", "billing backoff", "--provider", "none", *self.base_args()]
        )
        transition, transition_stdout, _ = self.invoke(
            [
                "record-state",
                "retry-policy",
                "--review",
                "accepted",
                "--reason",
                "Reviewed source evidence.",
                "--provider",
                "none",
                *self.base_args(),
            ]
        )
        active, active_stdout, _ = self.invoke(
            ["search", "billing backoff", "--provider", "none", *self.base_args()]
        )

        self.assertEqual(0, inactive)
        self.assertEqual([], json.loads(inactive_stdout)["records"])
        self.assertEqual(0, transition)
        event = Path(json.loads(transition_stdout)["event"])
        self.assertTrue(event.is_file())
        self.assertEqual(original, self.record.read_bytes())
        saved = self.home / "records" / self.project_slug() / "retry-policy.md"
        self.assertEqual(original, saved.read_bytes())
        self.assertEqual(0, active)
        self.assertEqual("retry-policy", json.loads(active_stdout)["records"][0]["id"])

    def test_state_event_rejects_mismatched_record_hash(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        event_dir = self.home / "states" / self.project_slug() / "retry-policy"
        event_dir.mkdir(parents=True)
        (event_dir / "bad.json").write_text(
            json.dumps(
                {
                    "schema": memory_provider.STATE_SCHEMA,
                    "event_id": "bad",
                    "record_id": "retry-policy",
                    "record_hash": "0" * 64,
                    "project": "mbeacom/context-kit",
                    "project_key": self.project_slug(),
                    "timestamp": "2026-07-19T13:00:00-04:00",
                    "prior_review": "accepted",
                    "prior_freshness": "current",
                    "effective_review": "rejected",
                    "effective_freshness": "current",
                    "reason": "Bad binding.",
                }
            ),
            encoding="utf-8",
        )

        result, stdout, _ = self.invoke(["review", *self.base_args()])

        self.assertEqual(0, result)
        self.assertIn("does not bind", json.loads(stdout)["records"][0]["error"])

    def test_concurrent_state_transitions_remain_a_valid_chain(self) -> None:
        self.write_record(review="proposed")
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        config = memory_provider.Config(
            provider="none",
            home=self.home,
            project="mbeacom/context-kit",
            auto_capture=False,
        )
        accept = type(
            "Args",
            (),
            {
                "record_id": "retry-policy",
                "review": "accepted",
                "freshness": None,
                "reason": "Evidence review.",
            },
        )()
        stale = type(
            "Args",
            (),
            {
                "record_id": "retry-policy",
                "review": None,
                "freshness": "stale",
                "reason": "Source changed.",
            },
        )()
        with (
            patch("builtins.print"),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            list(
                executor.map(
                    lambda args: memory_provider._record_state(args, config),
                    (accept, stale),
                )
            )

        metadata, state = memory_provider._load_record(
            self.home / "records" / self.project_slug() / "retry-policy.md",
            config,
        )
        self.assertEqual("retry-policy", metadata["id"])
        self.assertEqual({"review": "accepted", "freshness": "stale"}, state)
        self.assertEqual(
            2,
            len(
                list(
                    (self.home / "states" / self.project_slug() / "retry-policy").glob(
                        "*.json"
                    )
                )
            ),
        )

    def test_audit_search_includes_inactive_records(self) -> None:
        self.write_record(review="proposed")
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )

        result, stdout, _ = self.invoke(
            [
                "search",
                "billing backoff",
                "--include-inactive",
                "--provider",
                "none",
                *self.base_args(),
            ]
        )

        self.assertEqual(0, result)
        self.assertEqual("proposed", json.loads(stdout)["records"][0]["review"])

    def test_sequenced_events_replay_when_wall_clock_moves_backward(self) -> None:
        self.write_record(review="proposed")
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        with patch.object(
            memory_provider, "_utc_timestamp", return_value="2026-07-19T13:00:00Z"
        ):
            accepted, _, _ = self.invoke(
                [
                    "record-state",
                    "retry-policy",
                    "--review",
                    "accepted",
                    "--reason",
                    "Evidence reviewed.",
                    "--provider",
                    "none",
                    *self.base_args(),
                ]
            )
        with patch.object(
            memory_provider, "_utc_timestamp", return_value="2026-07-19T12:00:00Z"
        ):
            stale, _, _ = self.invoke(
                [
                    "record-state",
                    "retry-policy",
                    "--freshness",
                    "stale",
                    "--reason",
                    "Source changed.",
                    "--provider",
                    "none",
                    *self.base_args(),
                ]
            )

        config = memory_provider.Config(
            provider="none",
            home=self.home,
            project="mbeacom/context-kit",
            auto_capture=False,
        )
        _, state = memory_provider._load_record(
            self.home / "records" / self.project_slug() / "retry-policy.md", config
        )
        names = sorted(
            path.name
            for path in (
                self.home / "states" / self.project_slug() / "retry-policy"
            ).glob("*.json")
        )
        self.assertEqual(0, accepted)
        self.assertEqual(0, stale)
        self.assertTrue(names[0].startswith("00000000000000000001-"))
        self.assertTrue(names[1].startswith("00000000000000000002-"))
        self.assertEqual({"review": "accepted", "freshness": "stale"}, state)

    def test_stale_state_lock_is_reclaimed_but_live_lock_is_refused(self) -> None:
        self.write_record(review="proposed")
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        lock = self.home / "states" / self.project_slug() / "retry-policy" / ".lock"
        lock.mkdir(parents=True)
        (lock / "owner.json").write_text(
            json.dumps(
                {"pid": 999999, "token": "dead", "acquired_at": "2026-01-01T00:00:00Z"}
            ),
            encoding="utf-8",
        )
        with patch.object(memory_provider.os, "kill", side_effect=ProcessLookupError):
            recovered, _, _ = self.invoke(
                [
                    "record-state",
                    "retry-policy",
                    "--review",
                    "accepted",
                    "--reason",
                    "Recovered stale lock.",
                    "--provider",
                    "none",
                    *self.base_args(),
                ]
            )
        lock.mkdir()
        (lock / "owner.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "token": "live",
                    "acquired_at": "2026-01-01T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        with patch.object(memory_provider, "STATE_LOCK_TIMEOUT_SECONDS", 0):
            refused, _, stderr = self.invoke(
                [
                    "record-state",
                    "retry-policy",
                    "--freshness",
                    "stale",
                    "--reason",
                    "Should not steal lock.",
                    "--provider",
                    "none",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, recovered)
        self.assertEqual(2, refused)
        self.assertIn("busy", stderr)

    def test_capture_rejects_repository_project_mismatch(self) -> None:
        result, _, stderr = self.invoke(
            [
                "capture",
                str(self.record),
                "--provider",
                "none",
                "--home",
                str(self.home),
                "--project",
                "other/repository",
            ]
        )

        self.assertEqual(2, result)
        self.assertIn("does not match", stderr)

    def test_selected_provider_fails_clearly_when_cli_is_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(memory_provider.shutil, "which", return_value=None),
        ):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(2, result)
        self.assertIn("not installed", stderr)

    def test_proposed_provider_capture_skips_archival_with_receipt(self) -> None:
        self.write_record(review="proposed")

        result, stdout, _ = self.invoke(
            [
                "capture",
                str(self.record),
                "--provider",
                "mempalace",
                *self.base_args(),
            ]
        )

        self.assertEqual(0, result)
        report = json.loads(stdout)
        self.assertFalse(report["provider_archived"])
        self.assertIn("not eligible", report["provider_archive"]["reason"])
        receipt = json.loads(
            Path(report["provider_archive"]["receipt"]).read_text(encoding="utf-8")
        )
        self.assertEqual("skipped", receipt["outcome"])
        self.assertEqual("not-invoked", receipt["provider_version"])

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_reports_compatibility_for_tested_mempalace_version(self) -> None:
        executable, _ = self.fake_mempalace()
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, stdout, _ = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(0, result)
        report = json.loads(stdout)
        self.assertEqual("ready", report["status"])
        compatibility = report["compatibility"]
        self.assertEqual("3.6.0", compatibility["parsed_version"])
        self.assertEqual("tested", compatibility["version_status"])
        self.assertEqual("3.6.x", compatibility["tested_release_line"])
        self.assertEqual("3.6.0", compatibility["tested_version"])
        self.assertEqual(str(executable), compatibility["executable"])
        self.assertIn(self.project_slug(), compatibility["palace_path"])
        capability_names = {
            c["name"]: c["status"] for c in compatibility["capabilities"]
        }
        self.assertEqual(
            {"capture": "ok", "search": "ok", "wake": "ok", "hook": "ok"},
            capability_names,
        )

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_refuses_clearly_when_capability_is_missing(self) -> None:
        executable, _ = self.fake_mempalace(
            help_overrides={"mine": "usage: mempalace mine DIR\n"}
        )
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(2, result)
        self.assertIn("missing required capabilities", stderr)
        self.assertIn("capture", stderr)
        self.assertIn("--wing", stderr)

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_refuses_clearly_when_subcommand_is_absent(self) -> None:
        executable, _ = self.fake_mempalace(exit_overrides={"hook run --help": 2})
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(2, result)
        self.assertIn("hook", stderr)
        self.assertIn("exited 2", stderr)

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_reports_older_version_without_hard_block(self) -> None:
        executable, _ = self.fake_mempalace(version_output="mempalace 3.5.4\n")
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, stdout, _ = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(0, result)
        compatibility = json.loads(stdout)["compatibility"]
        self.assertEqual("older-than-tested", compatibility["version_status"])
        self.assertEqual("3.5.4", compatibility["parsed_version"])

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_reports_newer_version_without_hard_block(self) -> None:
        executable, _ = self.fake_mempalace(version_output="mempalace 3.7.1\n")
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, stdout, _ = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(0, result)
        compatibility = json.loads(stdout)["compatibility"]
        self.assertEqual("newer-than-tested", compatibility["version_status"])
        self.assertEqual("3.7.1", compatibility["parsed_version"])

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_doctor_reports_unknown_version_when_unparseable(self) -> None:
        executable, _ = self.fake_mempalace(version_output="mempalace-dev-build\n")
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            result, stdout, _ = self.invoke(
                ["doctor", "--provider", "mempalace", *self.base_args()]
            )

        self.assertEqual(0, result)
        compatibility = json.loads(stdout)["compatibility"]
        self.assertEqual("unknown", compatibility["version_status"])
        self.assertIsNone(compatibility["parsed_version"])

    def test_portable_environment_precedes_claude_options(self) -> None:
        args = type("Args", (), {"provider": None, "home": None, "project": None})()
        with patch.dict(
            os.environ,
            {
                "CONTEXT_KIT_MEMORY_PROVIDER": "mempalace",
                "CLAUDE_PLUGIN_OPTION_PROVIDER": "none",
                "CONTEXT_KIT_MEMORY_HOME": str(self.home),
                "CLAUDE_PLUGIN_OPTION_MEMORY_HOME": str(self.root / "claude"),
                "CONTEXT_KIT_MEMORY_PROJECT": "portable/project",
                "CLAUDE_PLUGIN_OPTION_PROJECT": "claude/project",
            },
            clear=True,
        ):
            config = memory_provider._config(args)

        self.assertEqual("mempalace", config.provider)
        self.assertEqual(self.home.resolve(), config.home)
        self.assertEqual("portable/project", config.project)

    def test_disabled_hook_does_not_require_provider_or_project(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result, stdout, stderr = self.invoke(["hook", "stop"], b'{"event":"stop"}')

        self.assertEqual(0, result)
        self.assertEqual("{}\n", stdout)
        self.assertEqual("", stderr)

    def test_archive_handoff_preserves_verbatim_artifact(self) -> None:
        handoff = self.root / "handoff.md"
        handoff.write_text(self.valid_handoff(), encoding="utf-8")

        with patch.object(memory_provider, "_assert_handoff_current"):
            result, stdout, _ = self.invoke(
                [
                    "archive-handoff",
                    str(handoff),
                    "--provider",
                    "none",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, result)
        saved = Path(json.loads(stdout)["artifact"])
        self.assertEqual(handoff.read_bytes(), saved.read_bytes())

    def test_archive_handoff_rejects_repository_project_mismatch(self) -> None:
        handoff = self.root / "handoff.md"
        handoff.write_text(self.valid_handoff(), encoding="utf-8")

        with patch.object(memory_provider, "_assert_handoff_current"):
            result, _, stderr = self.invoke(
                [
                    "archive-handoff",
                    str(handoff),
                    "--provider",
                    "none",
                    "--home",
                    str(self.home),
                    "--project",
                    "other/repository",
                ]
            )

        self.assertEqual(2, result)
        self.assertIn("does not match", stderr)

    def test_handoff_validation_matches_authoritative_structure(self) -> None:
        missing_title = self.root / "missing-title.md"
        missing_title.write_text(
            self.valid_handoff().replace("# Context Handoff\n\n", ""),
            encoding="utf-8",
        )
        empty_section = self.root / "empty-section.md"
        empty_section.write_text(
            self.valid_handoff().replace("## Decisions\n\n- value", "## Decisions\n"),
            encoding="utf-8",
        )

        for path in (missing_title, empty_section):
            with self.subTest(path=path):
                with self.assertRaises(memory_provider.Refusal):
                    memory_provider.validate_handoff(path)

    def test_handoff_uses_300_line_limit(self) -> None:
        handoff = self.root / "long-handoff.md"
        prose = "\n".join(f"evidence line {index}" for index in range(230))
        text = self.valid_handoff().replace(
            "## Verified Facts\n\n- value",
            f"## Verified Facts\n\n{prose}",
        )
        handoff.write_text(text, encoding="utf-8")

        metadata = memory_provider.validate_handoff(handoff)

        self.assertGreater(len(text.splitlines()), memory_provider.MAX_MEMORY_LINES)
        self.assertLessEqual(len(text.splitlines()), memory_provider.MAX_HANDOFF_LINES)
        self.assertEqual("context-kit/handoff-v1", metadata["schema"])

    def test_handoff_rejects_fenced_extra_level_two_heading(self) -> None:
        handoff = self.root / "fenced-heading.md"
        handoff.write_text(
            self.valid_handoff().replace(
                "## Verified Facts\n\n- value",
                "\n".join(
                    [
                        "## Verified Facts",
                        "",
                        "```markdown",
                        "## Extra",
                        "```",
                    ]
                ),
            ),
            encoding="utf-8",
        )

        with self.assertRaises(memory_provider.Refusal):
            memory_provider.validate_handoff(handoff)

    def test_handoff_normalizes_heading_whitespace(self) -> None:
        handoff = self.root / "heading-whitespace.md"
        handoff.write_text(
            self.valid_handoff().replace("## Scope\n", "## Scope   \n"),
            encoding="utf-8",
        )

        metadata = memory_provider.validate_handoff(handoff)

        self.assertEqual("context-kit/handoff-v1", metadata["schema"])

    def test_handoff_archival_rejects_stale_repository_context(self) -> None:
        handoff = self.root / "handoff.md"
        handoff.write_text(self.valid_handoff(), encoding="utf-8")
        metadata = memory_provider.validate_handoff(handoff)

        def fake_git(_repo, *argv):
            responses = {
                ("rev-parse", "--show-toplevel"): str(self.root),
                (
                    "remote",
                    "get-url",
                    "origin",
                ): "https://github.com/mbeacom/context-kit.git",
                ("branch", "--show-current"): "main",
                ("rev-parse", "HEAD"): "different-head",
                ("merge-base", "HEAD", "main"): "abcdef0123456789",
                ("status", "--porcelain"): "",
            }
            return responses[argv]

        with (
            patch.object(memory_provider, "_git", side_effect=fake_git),
            self.assertRaisesRegex(memory_provider.Refusal, "saved=.*current="),
        ):
            memory_provider._assert_handoff_current(metadata, self.root)

    def test_review_flags_drifted_source(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        self.source.write_text("changed\n", encoding="utf-8")

        result, stdout, _ = self.invoke(["review", *self.base_args()])

        self.assertEqual(0, result)
        entry = json.loads(stdout)["records"][0]
        self.assertEqual("drifted", entry["source_state"])

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_provider_capture_uses_exact_scoped_argv(self) -> None:
        executable, calls = self.fake_mempalace()
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)},
            clear=True,
        ):
            result, stdout, _ = self.invoke(
                [
                    "capture",
                    str(self.record),
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, result)
        self.assertTrue(json.loads(stdout)["provider_archived"])
        provider_receipt = Path(json.loads(stdout)["provider_archive"]["receipt"])
        self.assertTrue(provider_receipt.is_file())
        call = next(
            json.loads(line)
            for line in calls.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["argv"][0] == "mine"
        )
        self.assertEqual("mine", call["argv"][0])
        self.assertEqual(["--wing", self.project_slug()], call["argv"][-2:])
        self.assertIn(
            f"providers/mempalace/{self.project_slug()}/palace",
            call["palace"],
        )

    @unittest.skipUnless(os.name == "posix", "safe directory swap requires POSIX")
    def test_provider_sync_dry_run_and_apply_preserves_backup(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        executable, _ = self.fake_mempalace()
        palace = self.home / "providers" / "mempalace" / self.project_slug() / "palace"
        palace.mkdir(parents=True)
        (palace / "old.txt").write_text("old palace", encoding="utf-8")
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)},
            clear=True,
        ):
            dry, dry_stdout, _ = self.invoke(
                ["sync-provider", "--provider", "mempalace", *self.base_args()]
            )
            apply, apply_stdout, _ = self.invoke(
                [
                    "sync-provider",
                    "--apply",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, dry)
        self.assertEqual("dry-run", json.loads(dry_stdout)["status"])
        self.assertEqual(0, apply)
        report = json.loads(apply_stdout)
        backup = Path(report["backup_path"])
        self.assertTrue(backup.is_dir())
        self.assertEqual("old palace", (backup / "old.txt").read_text(encoding="utf-8"))
        self.assertTrue(Path(report["receipt"]).is_file())

    @unittest.skipUnless(os.name == "posix", "safe directory swap requires POSIX")
    def test_provider_marker_rejects_reverted_active_projection_until_resynced(
        self,
    ) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        second = self.root / "second.md"
        second.write_text(
            self.record.read_text(encoding="utf-8").replace(
                "id: retry-policy", "id: second-policy"
            ),
            encoding="utf-8",
        )
        executable, _ = self.fake_mempalace()
        with patch.dict(
            os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
        ):
            first_sync, _, _ = self.invoke(
                [
                    "sync-provider",
                    "--apply",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            self.invoke(
                ["capture", str(second), "--provider", "none", *self.base_args()]
            )
            second_sync, _, _ = self.invoke(
                [
                    "sync-provider",
                    "--apply",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            rejected, _, _ = self.invoke(
                [
                    "record-state",
                    "second-policy",
                    "--review",
                    "rejected",
                    "--reason",
                    "Superseded by current policy.",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            search, _, stderr = self.invoke(
                [
                    "search",
                    "retry",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, first_sync)
        self.assertEqual(0, second_sync)
        self.assertEqual(0, rejected)
        self.assertEqual(2, search)
        self.assertIn("sync-provider --apply", stderr)

    @unittest.skipUnless(os.name == "posix", "safe directory swap requires POSIX")
    def test_failed_swap_receipt_records_restored_live_palace(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        executable, _ = self.fake_mempalace()
        palace = self.home / "providers" / "mempalace" / self.project_slug() / "palace"
        palace.mkdir(parents=True)
        (palace / "old.txt").write_text("old palace", encoding="utf-8")
        real_replace = os.replace

        def fail_stage_swap(source, target):
            if Path(source).name.startswith(".palace-rebuild-"):
                raise OSError("simulated stage swap failure")
            return real_replace(source, target)

        with (
            patch.dict(
                os.environ, {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)}, clear=True
            ),
            patch.object(memory_provider.os, "replace", side_effect=fail_stage_swap),
        ):
            result, _, _ = self.invoke(
                [
                    "sync-provider",
                    "--apply",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        receipt = json.loads(
            sorted((self.home / "receipts" / self.project_slug()).glob("*.json"))[
                -1
            ].read_text(encoding="utf-8")
        )
        self.assertEqual(2, result)
        self.assertEqual("failed", receipt["outcome"])
        self.assertIsNone(receipt["backup_path"])
        self.assertEqual("restored-to-live-palace", receipt["recovery_status"])
        self.assertEqual("old palace", (palace / "old.txt").read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_search_forwards_exact_query_and_result_limit(self) -> None:
        executable, calls = self.fake_mempalace(stdout="remembered evidence\n")
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)},
            clear=True,
        ):
            capture, _, _ = self.invoke(
                [
                    "capture",
                    str(self.record),
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            sync, _, _ = self.invoke(
                [
                    "sync-provider",
                    "--apply",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            result, stdout, _ = self.invoke(
                [
                    "search",
                    "why retries",
                    "--results",
                    "4",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        self.assertEqual(0, capture)
        self.assertEqual(0, sync)
        self.assertEqual(0, result)
        self.assertEqual("remembered evidence\n", stdout)
        call = [
            json.loads(line)
            for line in calls.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["argv"][0] == "search"
        ][0]
        self.assertEqual(["search", "why retries", "--results", "4"], call["argv"])

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_provider_search_refuses_until_active_index_is_reconciled(self) -> None:
        executable, _ = self.fake_mempalace()
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)},
            clear=True,
        ):
            self.invoke(
                [
                    "capture",
                    str(self.record),
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )
            result, _, stderr = self.invoke(
                [
                    "search",
                    "billing backoff",
                    "--provider",
                    "mempalace",
                    *self.base_args(),
                ]
            )

        self.assertEqual(2, result)
        self.assertIn("sync-provider --apply", stderr)

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_enabled_hook_forwards_payload_and_scopes_palace(self) -> None:
        executable, calls = self.fake_mempalace(stdout="{}")
        payload = b'{"event":"stop","session_id":"abc"}'
        with patch.dict(
            os.environ,
            {
                "CONTEXT_KIT_MEMPALACE_BIN": str(executable),
                "CONTEXT_KIT_MEMORY_PROVIDER": "mempalace",
                "CONTEXT_KIT_MEMORY_HOME": str(self.home),
                "CONTEXT_KIT_MEMORY_PROJECT": "mbeacom/context-kit",
                "CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "true",
            },
            clear=True,
        ):
            result, stdout, _ = self.invoke(["hook", "stop"], payload)

        self.assertEqual(0, result)
        self.assertEqual("{}", stdout)
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(
            ["hook", "run", "--hook", "stop", "--harness", "claude-code"],
            call["argv"],
        )
        self.assertEqual(payload.decode(), call["stdin"])

    #: Default `--help` bodies that satisfy every required capability probe
    #: in `memory_provider._required_mempalace_capabilities()` for the
    #: MemPalace 3.6.0 release the adapter is tested against. Tests override
    #: individual topics to model missing/incompatible upstream CLI surfaces.
    DEFAULT_HELP_TOPICS = {
        "mine": "usage: mempalace mine DIR --wing WING\n",
        "search": "usage: mempalace search QUERY --results N\n",
        "wake-up": "usage: mempalace wake-up\n",
        "hook": "usage: mempalace hook run --hook EVENT --harness HARNESS\n",
    }

    def fake_mempalace(
        self,
        stdout: str = "",
        *,
        version_output: str = "mempalace 3.6.0\n",
        help_overrides: dict[str, str] | None = None,
        exit_overrides: dict[str, int] | None = None,
    ) -> tuple[Path, Path]:
        """Write a fake `mempalace` executable that logs every call.

        By default it answers `--version` and `<topic> --help` with output
        that satisfies every required capability probe, so tests only need to
        override the specific topic(s) they want to model as missing,
        incompatible, or drifted.
        """
        help_topics = dict(self.DEFAULT_HELP_TOPICS)
        help_topics.update(help_overrides or {})
        executable = self.root / "mempalace"
        calls = self.root / "calls.jsonl"
        executable.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    f"calls = {str(calls)!r}",
                    "argv = sys.argv[1:]",
                    "record = {",
                    "  'argv': argv,",
                    "  'stdin': sys.stdin.read(),",
                    "  'palace': os.environ.get('MEMPALACE_PALACE_PATH'),",
                    "}",
                    "with open(calls, 'a', encoding='utf-8') as handle:",
                    "    handle.write(json.dumps(record) + '\\n')",
                    f"help_topics = {help_topics!r}",
                    f"exit_overrides = {(exit_overrides or {})!r}",
                    "key = ' '.join(argv)",
                    "if key in exit_overrides:",
                    "    sys.exit(exit_overrides[key])",
                    "if argv == ['--version']:",
                    f"    sys.stdout.write({version_output!r})",
                    "    sys.exit(0)",
                    "if argv and argv[-1] == '--help':",
                    "    sys.stdout.write(help_topics.get(argv[0], 'usage: mempalace\\n'))",
                    "    sys.exit(0)",
                    f"sys.stdout.write({stdout!r})",
                ]
            ),
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable, calls

    @staticmethod
    def valid_handoff() -> str:
        headings = [
            "## Scope",
            "## Verified Facts",
            "## Decisions",
            "## Changed Files",
            "## Completed Work",
            "## Unresolved Items",
            "## Next Steps",
            "## Validation State",
            "## Provenance and Freshness",
        ]
        header = "\n".join(
            [
                "---",
                "schema: context-kit/handoff-v1",
                "generated_at: 2026-07-19T12:00:00-04:00",
                "repository: mbeacom/context-kit",
                "worktree: /tmp/context-kit",
                "branch: main",
                "head: abcdef0123456789",
                "base_ref: main",
                "base_commit: abcdef0123456789",
                "worktree_state: clean",
                "---",
                "",
                "# Context Handoff",
                "",
                "",
            ]
        )
        return (
            header + "\n\n".join(f"{heading}\n\n- value" for heading in headings) + "\n"
        )


if __name__ == "__main__":
    unittest.main()
