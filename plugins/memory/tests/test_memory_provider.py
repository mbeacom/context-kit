from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
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
        self, *, cues: list[str] | None = None, source_hash: str | None = None
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
                    "freshness: current",
                    "review: accepted",
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

    def test_local_capture_is_idempotent(self) -> None:
        argv = ["capture", str(self.record), "--provider", "none", *self.base_args()]

        first, first_stdout, _ = self.invoke(argv)
        second, second_stdout, _ = self.invoke(argv)

        self.assertEqual(0, first)
        self.assertEqual(0, second)
        self.assertEqual("created", json.loads(first_stdout)["status"])
        self.assertEqual("unchanged", json.loads(second_stdout)["status"])
        saved = self.home / "records" / "mbeacom-context-kit" / "retry-policy.md"
        self.assertEqual(self.record.read_bytes(), saved.read_bytes())

    def test_doctor_reports_disabled_provider(self) -> None:
        result, stdout, _ = self.invoke(
            ["doctor", "--provider", "none", *self.base_args()]
        )

        self.assertEqual(0, result)
        self.assertEqual("disabled", json.loads(stdout)["status"])

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
        self.assertEqual("invalid-or-stale", entry["source_state"])

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
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual("mine", call["argv"][0])
        self.assertEqual(["--wing", "mbeacom-context-kit"], call["argv"][-2:])
        self.assertIn(
            "providers/mempalace/mbeacom-context-kit/palace",
            call["palace"],
        )

    @unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
    def test_search_forwards_exact_query_and_result_limit(self) -> None:
        executable, calls = self.fake_mempalace(stdout="remembered evidence\n")
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_MEMPALACE_BIN": str(executable)},
            clear=True,
        ):
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

        self.assertEqual(0, result)
        self.assertEqual("remembered evidence\n", stdout)
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(["search", "why retries", "--results", "4"], call["argv"])

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

    def fake_mempalace(self, stdout: str = "") -> tuple[Path, Path]:
        executable = self.root / "mempalace"
        calls = self.root / "calls.jsonl"
        executable.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    f"calls = {str(calls)!r}",
                    "record = {",
                    "  'argv': sys.argv[1:],",
                    "  'stdin': sys.stdin.read(),",
                    "  'palace': os.environ.get('MEMPALACE_PALACE_PATH'),",
                    "}",
                    "with open(calls, 'a', encoding='utf-8') as handle:",
                    "    handle.write(json.dumps(record) + '\\n')",
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
            ]
        )
        return (
            header + "\n\n".join(f"{heading}\n\n- value" for heading in headings) + "\n"
        )


if __name__ == "__main__":
    unittest.main()
