from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "src" / "memorykit" / "provider.py"
HOOKS = PLUGIN_ROOT / "hooks" / "hooks.json"
SPEC = importlib.util.spec_from_file_location("memory_provider_lifecycle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
memory_provider = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_provider
SPEC.loader.exec_module(memory_provider)


class LifecycleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "memory"
        self.sources = self.root / "sources"
        self.sources.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def invoke(self, argv: list[str], stdin: bytes = b"{}") -> tuple[int, str, str]:
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

    def add_record(
        self,
        record_id: str,
        *,
        observed_at: str = "2026-01-01T00:00:00Z",
        kind: str = "decision",
        primary: str = "A durable decision worth remembering later.",
        accept: bool = True,
    ) -> Path:
        source = self.sources / f"{record_id}.txt"
        source.write_text(f"evidence for {record_id}\n", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        artifact = self.root / f"{record_id}.md"
        artifact.write_text(
            "\n".join(
                [
                    "---",
                    "schema: context-kit/memory-v1",
                    f"id: {record_id}",
                    f"type: {kind}",
                    "scope: project",
                    "repository: mbeacom/context-kit",
                    "branch: main",
                    "head: 1234567",
                    f"observed_at: {observed_at}",
                    f"captured_at: {observed_at}",
                    "freshness: current",
                    "review: proposed",
                    f"source: {source}",
                    f"source_hash: {digest}",
                    "---",
                    "",
                    "## Primary Memory",
                    "",
                    primary,
                    "",
                    "## Cue Anchors",
                    "",
                    f"- {record_id} cue",
                    "",
                    "## Evidence",
                    "",
                    f"- `{source}:1` — captured evidence.",
                    "",
                    "## Supersedes",
                    "",
                    "- None.",
                    "",
                    "## Review Notes",
                    "",
                    "- Lifecycle test record.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.invoke(["capture", str(artifact), *self.base_args()])
        if accept:
            self.invoke(
                [
                    "record-state",
                    record_id,
                    "--review",
                    "accepted",
                    "--reason",
                    "Checked the cited evidence.",
                    *self.base_args(),
                ]
            )
        return source


class WakeDigestTests(LifecycleTestCase):
    """`wake` primes a session from records, not from a provider store."""

    def wake(self, *extra: str) -> dict[str, object]:
        result, stdout, stderr = self.invoke(["wake", *self.base_args(), *extra])
        self.assertEqual(0, result, stderr)
        return json.loads(stdout)

    def test_empty_store_produces_no_context(self) -> None:
        digest = self.wake()
        self.assertEqual(0, digest["counts"]["active"])
        # Nothing to say means an empty block, not a header with no content.
        self.assertEqual("", digest["context"])

    def test_only_active_records_are_surfaced(self) -> None:
        self.add_record("accepted-one")
        self.add_record("still-proposed", accept=False)
        digest = self.wake()
        self.assertEqual(["accepted-one"], [m["id"] for m in digest["memories"]])
        self.assertEqual(1, digest["counts"]["active"])
        self.assertEqual(1, digest["counts"]["inactive"])

    def test_records_are_ordered_by_recency(self) -> None:
        self.add_record("oldest", observed_at="2026-01-01T00:00:00Z")
        self.add_record("newest", observed_at="2026-06-01T00:00:00Z")
        self.add_record("middle", observed_at="2026-03-01T00:00:00Z")
        digest = self.wake()
        self.assertEqual(
            ["newest", "middle", "oldest"], [m["id"] for m in digest["memories"]]
        )

    def test_digest_is_bounded_by_record_count(self) -> None:
        limit = memory_provider.MAX_WAKE_RECORDS
        for index in range(limit + 4):
            self.add_record(
                f"record-{index:03d}",
                observed_at=f"2026-01-{index + 1:02d}T00:00:00Z",
            )
        digest = self.wake()
        self.assertEqual(limit, len(digest["memories"]))
        self.assertTrue(digest["truncated"])
        self.assertEqual(limit + 4, digest["counts"]["active"])
        # The block must say it is partial rather than implying completeness.
        self.assertIn("Showing", digest["context"])

    def test_digest_is_bounded_by_characters(self) -> None:
        for index in range(6):
            self.add_record(
                f"verbose-{index}",
                observed_at=f"2026-02-{index + 1:02d}T00:00:00Z",
                primary="x" * 580,
            )
        digest = self.wake()
        self.assertTrue(digest["truncated"])
        self.assertLess(len(digest["memories"]), 6)

    def test_drift_is_flagged_in_the_digest(self) -> None:
        source = self.add_record("drifting")
        source.write_text("mutated after capture\n", encoding="utf-8")
        digest = self.wake()
        self.assertEqual("drifted", digest["memories"][0]["source_state"])
        self.assertEqual(["drifting"], [a["id"] for a in digest["attention"]])
        self.assertIn("source changed", digest["context"])
        self.assertIn("audit", digest["context"])

    def test_missing_source_is_flagged(self) -> None:
        source = self.add_record("vanishing")
        source.unlink()
        digest = self.wake()
        self.assertEqual("unavailable", digest["memories"][0]["source_state"])
        self.assertEqual("unavailable", digest["attention"][0]["issue"])

    def test_text_format_emits_only_the_context_block(self) -> None:
        self.add_record("plain")
        result, stdout, stderr = self.invoke(
            ["wake", "--format", "text", *self.base_args()]
        )
        self.assertEqual(0, result, stderr)
        self.assertIn("Durable project memory", stdout)
        # Text mode is for injection, so it must not emit JSON envelope keys.
        self.assertNotIn('"schema"', stdout)

    def test_wake_works_without_a_provider(self) -> None:
        self.add_record("local-only")
        digest = self.wake("--provider", "none")
        self.assertEqual("none", digest["provider"])
        # Reconciliation is meaningless with no provider store.
        self.assertNotIn("reconciled", digest)


class SessionStartRecallHookTests(LifecycleTestCase):
    """SessionStart is the one point where memory pays for itself unasked."""

    def hook(self, event: str, env: dict[str, str] | None = None) -> dict[str, object]:
        base = {
            "CONTEXT_KIT_MEMORY_HOME": str(self.home),
            "CONTEXT_KIT_MEMORY_PROJECT": "mbeacom/context-kit",
        }
        base.update(env or {})
        with patch.dict(os.environ, base, clear=True):
            result, stdout, stderr = self.invoke(["hook", event])
        self.assertEqual(0, result, stderr)
        return json.loads(stdout)

    def test_recall_is_inert_by_default(self) -> None:
        self.add_record("private")
        # Shipping a hook that injects by default would surprise users on both
        # hosts that load hooks.json.
        self.assertEqual({}, self.hook("session-start"))

    def test_recall_emits_additional_context_when_enabled(self) -> None:
        self.add_record("retry-policy", primary="Retries cap at five attempts.")
        payload = self.hook(
            "session-start", {"CONTEXT_KIT_MEMORY_RECALL_ON_START": "true"}
        )
        self.assertEqual(["additionalContext"], list(payload))
        self.assertIn("Retries cap at five attempts.", payload["additionalContext"])

    def test_recall_is_bounded(self) -> None:
        for index in range(memory_provider.MAX_WAKE_RECORDS + 6):
            self.add_record(
                f"r{index:03d}",
                observed_at=f"2026-01-{index + 1:02d}T00:00:00Z",
                primary="y" * 300,
            )
        payload = self.hook(
            "session-start", {"CONTEXT_KIT_MEMORY_RECALL_ON_START": "true"}
        )
        # A session-priming block competes with real work for context.
        self.assertLess(
            len(payload["additionalContext"]), memory_provider.MAX_WAKE_CHARS * 2
        )

    def test_recall_emits_nothing_when_there_is_no_memory(self) -> None:
        self.assertEqual(
            {},
            self.hook("session-start", {"CONTEXT_KIT_MEMORY_RECALL_ON_START": "true"}),
        )

    def test_recall_never_breaks_a_session(self) -> None:
        # No project configured is a refusal everywhere else; in a hook it must
        # degrade to silence rather than failing the session start.
        with patch.dict(
            os.environ,
            {
                "CONTEXT_KIT_MEMORY_HOME": str(self.home),
                "CONTEXT_KIT_MEMORY_RECALL_ON_START": "true",
            },
            clear=True,
        ):
            result, stdout, _ = self.invoke(["hook", "session-start"])
        self.assertEqual(0, result)
        self.assertEqual({}, json.loads(stdout))

    def test_recall_does_not_depend_on_the_capture_switch(self) -> None:
        # Reading is not writing; the two are governed separately.
        self.add_record("readable")
        payload = self.hook(
            "session-start",
            {
                "CONTEXT_KIT_MEMORY_RECALL_ON_START": "true",
                "CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "false",
            },
        )
        self.assertIn("additionalContext", payload)


class CaptureBoundaryHookTests(LifecycleTestCase):
    def test_boundary_hooks_stay_inert_by_default(self) -> None:
        for event in ("stop", "precompact", "session-end"):
            with self.subTest(event=event):
                with patch.dict(
                    os.environ,
                    {
                        "CONTEXT_KIT_MEMORY_HOME": str(self.home),
                        "CONTEXT_KIT_MEMORY_PROJECT": "mbeacom/context-kit",
                    },
                    clear=True,
                ):
                    result, stdout, _ = self.invoke(["hook", event], b'{"a": 1}')
                self.assertEqual(0, result)
                self.assertEqual({}, json.loads(stdout))
        self.assertFalse((self.home / "pending-hooks").exists())

    def test_enabled_boundary_hooks_queue_for_review_without_capturing(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CONTEXT_KIT_MEMORY_HOME": str(self.home),
                "CONTEXT_KIT_MEMORY_PROJECT": "mbeacom/context-kit",
                "CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "true",
            },
            clear=True,
        ):
            result, stdout, _ = self.invoke(["hook", "stop"], b'{"transcript": "x"}')
        self.assertEqual(0, result)
        payload = json.loads(stdout)
        self.assertEqual("queued-for-review", payload["status"])
        self.assertFalse(payload["provider_invoked"])
        # Queuing is not capturing: no memory record may exist yet.
        self.assertFalse((self.home / "records").exists())

    def test_shipped_hooks_cover_boundaries_and_not_tool_calls(self) -> None:
        configured = set(json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"])
        self.assertEqual(
            {"SessionStart", "Stop", "PreCompact", "SessionEnd"}, configured
        )
        # Measured on a real corpus, PreToolUse/PostToolUse fire tens of
        # thousands of times per corpus versus ~1,800 for these boundaries.
        # Hooking them would spawn a process per tool call and capture noise.
        self.assertNotIn("PreToolUse", configured)
        self.assertNotIn("PostToolUse", configured)


class CopilotSessionBindingTests(LifecycleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(
            ["git", "init", "-q"],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://github.com/mbeacom/context-kit.git",
            ],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )
        self.session_id = "ccb7ee61-57da-4533-b123-01afb28876f6"

    def hook_payload(
        self,
        event: str,
        *,
        cwd: Path | None = None,
        environment_session_id: str | None = None,
        payload_session_id: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        environment_session_id = environment_session_id or self.session_id
        payload_session_id = payload_session_id or self.session_id
        environment = {
            "CONTEXT_KIT_MEMORY_HOME": str(self.home),
            memory_provider.COPILOT_SESSION_ID_ENV: environment_session_id,
        }
        environment.update(extra_env or {})
        payload = json.dumps(
            {
                "cwd": str(cwd or self.repo),
                "sessionId": payload_session_id,
            }
        ).encode()
        with patch.dict(os.environ, environment, clear=True):
            return self.invoke(["hook", event], payload)

    def binding_path(self, session_id: str | None = None) -> Path:
        return (
            self.home
            / memory_provider.SESSION_BINDING_DIRNAME
            / f"{session_id or self.session_id}.json"
        )

    def test_trusted_session_start_creates_a_minimal_private_binding(self) -> None:
        result, stdout, stderr = self.hook_payload("session-start")

        self.assertEqual(0, result, stderr)
        self.assertEqual({}, json.loads(stdout))
        binding = self.binding_path()
        self.assertEqual(
            {
                "project": "mbeacom/context-kit",
                "session_id": self.session_id,
            },
            json.loads(binding.read_text(encoding="utf-8")),
        )
        if os.name == "posix":
            self.assertEqual(
                0o700,
                stat.S_IMODE(binding.parent.stat().st_mode),
            )
            self.assertEqual(0o600, stat.S_IMODE(binding.stat().st_mode))

    def test_session_environment_must_exactly_match_the_payload(self) -> None:
        result, stdout, stderr = self.hook_payload(
            "session-start",
            payload_session_id="another-session",
        )

        self.assertEqual(0, result, stderr)
        self.assertEqual({}, json.loads(stdout))
        self.assertFalse(self.binding_path().exists())

    def test_non_git_and_originless_directories_leave_memory_unbound(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        originless = self.root / "originless"
        originless.mkdir()
        subprocess.run(
            ["git", "init", "-q"],
            cwd=originless,
            check=True,
            capture_output=True,
        )

        for index, cwd in enumerate((plain, originless), start=1):
            session_id = f"missing-context-{index}"
            with self.subTest(cwd=cwd):
                result, stdout, stderr = self.hook_payload(
                    "session-start",
                    cwd=cwd,
                    environment_session_id=session_id,
                    payload_session_id=session_id,
                )
                self.assertEqual(0, result, stderr)
                self.assertEqual({}, json.loads(stdout))
                self.assertFalse(self.binding_path(session_id).exists())

    def test_project_precedence_keeps_explicit_configuration_authoritative(
        self,
    ) -> None:
        self.hook_payload("session-start")
        args = type(
            "Args",
            (),
            {"provider": None, "home": str(self.home), "project": None},
        )()
        environment = {
            memory_provider.COPILOT_SESSION_ID_ENV: self.session_id,
            "CONTEXT_KIT_MEMORY_PROJECT": "portable/project",
            "PRODUCTIVITY_SKILLS_MEMORY_PROJECT": "legacy/project",
            "CLAUDE_PLUGIN_OPTION_PROJECT": "claude/project",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual("portable/project", memory_provider._config(args).project)
            del os.environ["CONTEXT_KIT_MEMORY_PROJECT"]
            self.assertEqual("legacy/project", memory_provider._config(args).project)
            del os.environ["PRODUCTIVITY_SKILLS_MEMORY_PROJECT"]
            self.assertEqual("claude/project", memory_provider._config(args).project)
            del os.environ["CLAUDE_PLUGIN_OPTION_PROJECT"]
            self.assertEqual(
                "mbeacom/context-kit",
                memory_provider._config(args).project,
            )
            args.project = "argument/project"
            self.assertEqual("argument/project", memory_provider._config(args).project)

    def test_wrong_session_cannot_resolve_an_existing_binding(self) -> None:
        self.hook_payload("session-start")
        args = type(
            "Args",
            (),
            {"provider": None, "home": str(self.home), "project": None},
        )()
        with patch.dict(
            os.environ,
            {memory_provider.COPILOT_SESSION_ID_ENV: "different-session"},
            clear=True,
        ):
            self.assertIsNone(memory_provider._config(args).project)

    def test_resume_is_idempotent_and_cannot_rebind_to_another_project(self) -> None:
        self.hook_payload("session-start")
        binding = self.binding_path()
        original = binding.read_bytes()
        original_inode = binding.stat().st_ino

        self.hook_payload("session-start")
        self.assertEqual(original, binding.read_bytes())
        self.assertEqual(original_inode, binding.stat().st_ino)

        other = self.root / "other"
        other.mkdir()
        subprocess.run(
            ["git", "init", "-q"],
            cwd=other,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://github.com/someone/else.git",
            ],
            cwd=other,
            check=True,
            capture_output=True,
        )
        result, stdout, stderr = self.hook_payload("session-start", cwd=other)

        self.assertEqual(0, result)
        self.assertEqual({}, json.loads(stdout))
        self.assertIn("another project", stderr)
        self.assertEqual(
            {"project": "", "session_id": self.session_id},
            json.loads(binding.read_text(encoding="utf-8")),
        )
        args = type(
            "Args",
            (),
            {"provider": None, "home": str(self.home), "project": None},
        )()
        with (
            patch.dict(
                os.environ,
                {memory_provider.COPILOT_SESSION_ID_ENV: self.session_id},
                clear=True,
            ),
            self.assertRaisesRegex(memory_provider.Refusal, "invalid project"),
        ):
            memory_provider._config(args)

        repeated, _, repeated_stderr = self.hook_payload("session-start", cwd=other)
        self.assertEqual(0, repeated)
        self.assertIn("already conflicted", repeated_stderr)
        ended, _, ended_stderr = self.hook_payload(
            "session-end",
            cwd=other,
            extra_env={"CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "true"},
        )
        self.assertEqual(2, ended)
        self.assertIn("CONTEXT_KIT_MEMORY_PROJECT", ended_stderr)
        self.assertFalse(binding.exists())

    def test_session_end_cleans_only_a_matching_session_binding(self) -> None:
        self.hook_payload("session-start")
        binding = self.binding_path()
        self.assertTrue(binding.exists())

        result, stdout, stderr = self.hook_payload("session-end")

        self.assertEqual(0, result, stderr)
        self.assertEqual({}, json.loads(stdout))
        self.assertFalse(binding.exists())

    def test_session_end_queues_under_the_binding_before_cleanup(self) -> None:
        self.hook_payload("session-start")

        result, stdout, stderr = self.hook_payload(
            "session-end",
            extra_env={"CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "true"},
        )

        self.assertEqual(0, result, stderr)
        response = json.loads(stdout)
        self.assertEqual("queued-for-review", response["status"])
        pending = Path(response["pending"])
        expected_slug = memory_provider.Config(
            provider="none",
            home=self.home,
            project="mbeacom/context-kit",
            auto_capture=True,
        ).project_slug
        self.assertEqual(expected_slug, pending.parent.name)
        self.assertTrue(pending.is_file())
        self.assertFalse(self.binding_path().exists())

    def test_mismatched_session_end_and_stop_leave_the_binding_in_place(self) -> None:
        self.hook_payload("session-start")
        binding = self.binding_path()

        self.hook_payload("stop")
        self.assertTrue(binding.exists())
        self.hook_payload(
            "session-end",
            payload_session_id="another-session",
        )
        self.assertTrue(binding.exists())

    def test_unsafe_session_ids_and_permissions_are_refused(self) -> None:
        result, stdout, stderr = self.hook_payload(
            "session-start",
            environment_session_id="../escape",
            payload_session_id="../escape",
        )
        self.assertEqual(0, result, stderr)
        self.assertEqual({}, json.loads(stdout))
        self.assertFalse((self.home / "escape.json").exists())

        self.hook_payload("session-start")
        if os.name == "posix":
            self.binding_path().chmod(0o644)
            with self.assertRaisesRegex(memory_provider.Refusal, "permissions"):
                memory_provider._read_session_binding(self.home, self.session_id)

    @unittest.skipUnless(os.name == "posix", "symlink refusal requires POSIX")
    def test_symlinked_session_binding_is_refused(self) -> None:
        self.hook_payload("session-start")
        binding = self.binding_path()
        target = self.root / "outside.json"
        target.write_bytes(binding.read_bytes())
        binding.unlink()
        binding.symlink_to(target)

        with self.assertRaisesRegex(memory_provider.Refusal, "safely open"):
            memory_provider._read_session_binding(self.home, self.session_id)


class AuditTests(LifecycleTestCase):
    def audit(self, *extra: str) -> dict[str, object]:
        result, stdout, stderr = self.invoke(["audit", *self.base_args(), *extra])
        self.assertEqual(0, result, stderr)
        return json.loads(stdout)

    def test_clean_store_reports_no_findings(self) -> None:
        self.add_record("intact")
        report = self.audit()
        self.assertEqual([], report["findings"])
        self.assertEqual(1, report["counts"]["verified"])
        self.assertEqual(0, report["actionable"])

    def test_drifted_and_missing_sources_are_reported(self) -> None:
        drifted = self.add_record("drifted-record")
        drifted.write_text("changed\n", encoding="utf-8")
        missing = self.add_record("missing-record")
        missing.unlink()
        self.add_record("fine-record")

        report = self.audit()
        states = {f["id"]: f["source_state"] for f in report["findings"]}
        self.assertEqual(
            {"drifted-record": "drifted", "missing-record": "unavailable"}, states
        )
        self.assertEqual(1, report["counts"]["verified"])
        self.assertEqual(2, report["actionable"])

    def test_audit_never_mutates_anything(self) -> None:
        source = self.add_record("untouched")
        source.unlink()
        artifact = self.home / "records"
        before = sorted(p.read_bytes() for p in artifact.rglob("*.md"))
        self.audit()
        after = sorted(p.read_bytes() for p in artifact.rglob("*.md"))
        # Evidence is the reason a memory can be trusted later; a moved file is
        # not proof the decision was wrong, so audit proposes and never prunes.
        self.assertEqual(before, after)
        self.assertTrue(list(artifact.rglob("*.md")))

    def test_suggested_command_is_the_one_that_fixes_it(self) -> None:
        source = self.add_record("actionable-record")
        source.unlink()
        finding = self.audit()["findings"][0]
        self.assertIn("record-state actionable-record", finding["suggested"])
        self.assertIn("--freshness stale", finding["suggested"])

        result, _, stderr = self.invoke(
            [
                "record-state",
                "actionable-record",
                "--freshness",
                "stale",
                "--reason",
                "Cited source is no longer present; re-verify before relying on it.",
                *self.base_args(),
            ]
        )
        self.assertEqual(0, result, stderr)
        # Applying the suggestion removes it from the actionable set.
        self.assertEqual(0, self.audit()["actionable"])

    def test_inactive_records_are_reported_but_need_no_action(self) -> None:
        source = self.add_record("already-inactive", accept=False)
        source.unlink()
        report = self.audit()
        finding = report["findings"][0]
        self.assertFalse(finding["active"])
        self.assertIn("already inactive", finding["suggested"])
        self.assertEqual(0, report["actionable"])

    def test_limit_is_validated_and_reported(self) -> None:
        for index in range(4):
            source = self.add_record(f"broken-{index}")
            source.unlink()
        report = self.audit("--limit", "2")
        self.assertEqual(2, len(report["findings"]))
        self.assertTrue(report["truncated"])

        result, _, stderr = self.invoke(["audit", "--limit", "0", *self.base_args()])
        self.assertEqual(2, result)
        self.assertIn("at least 1", stderr)


if __name__ == "__main__":
    unittest.main()
