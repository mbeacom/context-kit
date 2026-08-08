from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "memory-provider.py"
SPEC = importlib.util.spec_from_file_location("memory_provider_rag", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
memory_provider = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_provider
SPEC.loader.exec_module(memory_provider)

INDEX_HELP = "usage: rag index [-h] [--name NAME] [--model MODEL] path\n"
QUERY_HELP = (
    "usage: rag query [-h] [--name NAME] [--k K] [--allowlist A] [--json] text\n"
)


@unittest.skipUnless(os.name == "posix", "fake executable requires POSIX")
class RagProviderTests(unittest.TestCase):
    """The first-party `rag` provider: offline semantic recall with no external tool.

    These exercise the adapter against a fake `rag` CLI so the contract is
    checked deterministically without ollama, embeddings, or a real index.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "memory"
        self.source = self.root / "source.txt"
        self.source.write_text("verified source\n", encoding="utf-8")
        self.record = self.root / "record.md"
        self.write_record()
        self.calls = self.root / "rag-calls.jsonl"
        self.rag_home = self.root / "rag-home"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_record(self, record_id: str = "retry-policy") -> Path:
        import hashlib

        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        path = self.root / f"{record_id}.md"
        path.write_text(
            "\n".join(
                [
                    "---",
                    "schema: context-kit/memory-v1",
                    f"id: {record_id}",
                    "type: decision",
                    "scope: project",
                    "repository: mbeacom/context-kit",
                    "branch: main",
                    "head: 1234567",
                    "observed_at: 2026-01-01T00:00:00Z",
                    "captured_at: 2026-01-01T00:00:00Z",
                    "freshness: current",
                    "review: accepted",
                    f"source: {self.source}",
                    f"source_hash: {digest}",
                    "---",
                    "",
                    "## Primary Memory",
                    "",
                    "A fixed five-attempt retry cap replaced exponential backoff.",
                    "",
                    "## Cue Anchors",
                    "",
                    "- retry policy",
                    "",
                    "## Evidence",
                    "",
                    f"- `{self.source}:1` — the captured source.",
                    "",
                    "## Supersedes",
                    "",
                    "- None.",
                    "",
                    "## Review Notes",
                    "",
                    "- Captured for the rag provider contract tests.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.record = path
        return path

    def invoke(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = memory_provider.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def base_args(self) -> list[str]:
        return ["--home", str(self.home), "--project", "mbeacom/context-kit"]

    def project_slug(self) -> str:
        return memory_provider.Config(
            provider="rag",
            home=self.home,
            project="mbeacom/context-kit",
            auto_capture=False,
        ).project_slug

    def fake_rag(
        self,
        *,
        query_result: object = None,
        version_output: str = "indexkit 0.6.0\n",
        help_overrides: dict[str, str] | None = None,
        exit_overrides: dict[str, int] | None = None,
    ) -> Path:
        """Write a fake `rag` executable that logs argv and the store env."""
        helps = {"index": INDEX_HELP, "query": QUERY_HELP}
        helps.update(help_overrides or {})
        if query_result is None:
            query_result = [
                {
                    "path": "retry-policy.md",
                    "heading": "Primary Memory",
                    "score": 271.5,
                    "retrieval_mode": "semantic",
                }
            ]
        executable = self.root / "rag"
        executable.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    f"calls = {str(self.calls)!r}",
                    "argv = sys.argv[1:]",
                    "with open(calls, 'a', encoding='utf-8') as handle:",
                    "    handle.write(json.dumps({",
                    "        'argv': argv,",
                    "        'data': os.environ.get('CONTEXT_KIT_DATA'),",
                    "        'home': os.environ.get('CONTEXT_KIT_INDEXKIT_HOME'),",
                    "    }) + '\\n')",
                    f"helps = {helps!r}",
                    f"exit_overrides = {(exit_overrides or {})!r}",
                    "key = ' '.join(argv)",
                    "if key in exit_overrides:",
                    "    sys.exit(exit_overrides[key])",
                    "if argv == ['--version']:",
                    f"    sys.stdout.write({version_output!r})",
                    "    sys.exit(0)",
                    "if len(argv) == 2 and argv[1] == '--help':",
                    "    sys.stdout.write(helps.get(argv[0], ''))",
                    "    sys.exit(0)",
                    "if argv and argv[0] == 'query':",
                    f"    sys.stdout.write(json.dumps({query_result!r}))",
                    "    sys.exit(0)",
                    "sys.exit(0)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        executable.chmod(0o700)
        return executable

    def env(self, executable: Path) -> dict[str, str]:
        return {
            "CONTEXT_KIT_INDEXKIT_BIN": str(executable),
            "CONTEXT_KIT_INDEXKIT_HOME": str(self.rag_home),
        }

    def recorded_calls(self) -> list[dict[str, object]]:
        if not self.calls.exists():
            return []
        return [
            json.loads(line)
            for line in self.calls.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def capture_and_sync(self, executable: Path) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, _, stderr = self.invoke(
                ["sync-provider", "--apply", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def test_rag_is_a_selectable_provider(self) -> None:
        self.assertIn("rag", memory_provider.PROVIDERS)
        self.assertIn("rag", memory_provider.PROVIDER_SPECS)

    def test_unknown_provider_is_refused(self) -> None:
        result, _, stderr = self.invoke(
            ["search", "retry", "--provider", "none", *self.base_args()]
        )
        self.assertEqual(0, result, stderr)
        with self.assertRaises(SystemExit):
            self.invoke(["search", "retry", "--provider", "bogus", *self.base_args()])

    def test_store_is_project_isolated(self) -> None:
        def store_for(project: str) -> Path:
            return memory_provider.Config(
                provider="rag",
                home=self.home,
                project=project,
                auto_capture=False,
            ).store_path

        first = store_for("mbeacom/context-kit")
        second = store_for("other/repository")
        self.assertNotEqual(first, second)
        # The rag store must not collide with the MemPalace layout either.
        self.assertIn("providers/rag/", str(first))

    # ------------------------------------------------------------------
    # doctor
    # ------------------------------------------------------------------

    def test_doctor_reports_ready_with_probed_capabilities(self) -> None:
        executable = self.fake_rag()
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual("ready", payload["status"])
        compatibility = payload["compatibility"]
        self.assertEqual("tested", compatibility["version_status"])
        self.assertEqual(
            {"ok"}, {probe["status"] for probe in compatibility["capabilities"]}
        )
        # A rag store is not a palace; the MemPalace-only key must not leak.
        self.assertNotIn("palace_path", compatibility)
        self.assertIn(self.project_slug(), compatibility["store_path"])

    def test_doctor_refuses_when_query_contract_drifts(self) -> None:
        # A rag build without --json would silently break hit mapping.
        executable = self.fake_rag(
            help_overrides={"query": "usage: rag query [-h] [--name NAME] text\n"}
        )
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(2, result)
        self.assertIn("missing option(s)", stderr)
        self.assertIn("--json", stderr)

    def test_doctor_refuses_when_a_capability_is_absent(self) -> None:
        executable = self.fake_rag(exit_overrides={"index --help": 2})
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(2, result)
        self.assertIn("missing required capabilities", stderr)

    # ------------------------------------------------------------------
    # reconciliation
    # ------------------------------------------------------------------

    def test_sync_dry_run_names_the_provider_and_changes_nothing(self) -> None:
        self.invoke(
            ["capture", str(self.record), "--provider", "none", *self.base_args()]
        )
        executable = self.fake_rag()
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["sync-provider", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        plan = json.loads(stdout)
        self.assertEqual("dry-run", plan["status"])
        self.assertEqual("rag", plan["provider"])
        self.assertEqual(["retry-policy"], plan["active_record_ids"])
        self.assertNotIn("palace_path", plan)
        self.assertEqual([], self.recorded_calls())

    def test_sync_indexes_the_projection_into_the_isolated_store(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)

        index_calls = [c for c in self.recorded_calls() if c["argv"][:1] == ["index"]]
        self.assertEqual(1, len(index_calls))
        call = index_calls[0]
        self.assertEqual("--name", call["argv"][2])
        self.assertEqual(memory_provider.RAG_INDEX_NAME, call["argv"][3])
        # Index data is redirected at the staged store...
        self.assertIn(".store-rebuild-", str(call["data"]))
        # ...while the venv home is preserved, or bin/rag could not start.
        self.assertEqual(str(self.rag_home), call["home"])

    def test_sync_writes_a_receipt_naming_the_rag_provider(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        receipts = sorted((self.home / "receipts" / self.project_slug()).glob("*.json"))
        payload = json.loads(receipts[-1].read_text(encoding="utf-8"))
        self.assertEqual("rag", payload["provider"])
        self.assertEqual("success", payload["outcome"])
        self.assertIn("providers/rag/", payload["store_path"])
        self.assertNotIn("palace_path", payload)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def test_search_maps_hits_back_to_records(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual("rag", payload["provider"])
        record = payload["records"][0]
        self.assertEqual("retry-policy", record["id"])
        # Provenance travels with the hit; a bare score is not a memory.
        self.assertEqual("accepted", record["review"])
        self.assertEqual("current", record["freshness"])
        self.assertEqual(str(self.source), record["source"])
        self.assertEqual("semantic", record["retrieval_mode"])
        self.assertEqual([], payload["unmatched_hits"])

    def test_search_reports_hits_it_cannot_bind_to_a_record(self) -> None:
        # An index ahead of the ledger must be visible, never silently dropped.
        executable = self.fake_rag(
            query_result=[
                {"path": "retry-policy.md", "score": 9.0},
                {"path": "ghost-record.md", "score": 8.0},
            ]
        )
        self.capture_and_sync(executable)
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual(["retry-policy"], [r["id"] for r in payload["records"]])
        self.assertEqual(["ghost-record.md"], payload["unmatched_hits"])

    def test_search_refuses_when_the_index_is_not_reconciled(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        # Revoking changes the active projection without touching the index.
        self.invoke(
            [
                "record-state",
                "retry-policy",
                "--freshness",
                "revoked",
                "--reason",
                "Superseded by a newer decision.",
                "--provider",
                "none",
                *self.base_args(),
            ]
        )
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, _, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        # Staleness is a correctness gate: it refuses instead of degrading.
        self.assertEqual(2, result)
        self.assertIn("not reconciled", stderr)
        self.assertNotIn("degraded_from", stderr)

    def test_search_degrades_explicitly_when_rag_is_unavailable(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        missing = self.root / "absent-rag"
        with patch.dict(
            os.environ,
            {
                "CONTEXT_KIT_INDEXKIT_BIN": str(missing),
                "CONTEXT_KIT_INDEXKIT_HOME": str(self.rag_home),
            },
            clear=True,
        ):
            result, stdout, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        # The fallback is lexical, and it says so rather than passing itself
        # off as semantic recall.
        self.assertEqual("local", payload["provider"])
        self.assertEqual("rag", payload["degraded_from"])
        self.assertIn("not runnable", payload["degraded_reason"])
        self.assertIn("lexical", payload["degraded_detail"])
        self.assertEqual(["retry-policy"], [r["id"] for r in payload["records"]])

    def test_reconciliation_gate_takes_precedence_over_degradation(self) -> None:
        # When the index is BOTH stale and unreachable, correctness wins: a
        # stale ledger must never be masked by a quiet lexical fallback.
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        self.invoke(
            [
                "record-state",
                "retry-policy",
                "--review",
                "rejected",
                "--reason",
                "Evidence did not support the claim.",
                "--provider",
                "none",
                *self.base_args(),
            ]
        )
        missing = self.root / "absent-rag"
        with patch.dict(
            os.environ,
            {"CONTEXT_KIT_INDEXKIT_BIN": str(missing)},
            clear=True,
        ):
            result, stdout, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(2, result)
        self.assertEqual("", stdout)
        self.assertIn("not reconciled", stderr)
        self.assertNotIn("degraded_from", stderr)

    def test_hits_are_deduplicated_back_to_records(self) -> None:
        # rag indexes each markdown section separately, so one record produces
        # several chunk hits. Without deduplication a single verbose memory
        # would consume the caller's whole result budget.
        executable = self.fake_rag(
            query_result=[
                {"path": "retry-policy.md", "heading": "Primary Memory", "score": 9.0},
                {"path": "retry-policy.md", "heading": "Cue Anchors", "score": 8.0},
                {"path": "retry-policy.md", "heading": "Evidence", "score": 7.0},
            ]
        )
        self.capture_and_sync(executable)
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["search", "retry", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual(["retry-policy"], [r["id"] for r in payload["records"]])
        record = payload["records"][0]
        # The strongest chunk wins and the rest are counted, not hidden.
        self.assertEqual(9.0, record["score"])
        self.assertEqual(3, record["matched_chunks"])

    def test_search_over_fetches_chunks_to_fill_the_record_budget(self) -> None:
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        with patch.dict(os.environ, self.env(executable), clear=True):
            self.invoke(
                [
                    "search",
                    "retry",
                    "--results",
                    "5",
                    "--provider",
                    "rag",
                    *self.base_args(),
                ]
            )
        query = [c for c in self.recorded_calls() if c["argv"][:1] == ["query"]][-1]
        requested = int(query["argv"][query["argv"].index("--k") + 1])
        # Asking rag for exactly 5 chunks could return one record five times.
        self.assertGreater(requested, 5)

    def test_capture_reports_reconciliation_for_any_provider(self) -> None:
        # An accepted capture is pending until sync, so reporting
        # "not-required" for rag while also writing a pending-sync receipt
        # would contradict the refusal search actually gives.
        executable = self.fake_rag()
        with patch.dict(os.environ, self.env(executable), clear=True):
            _, stdout, _ = self.invoke(
                ["capture", str(self.record), "--provider", "rag", *self.base_args()]
            )
        payload = json.loads(stdout)
        self.assertIn("required", payload["provider_reconciliation"])
        self.assertIn("sync-provider --apply", payload["provider_reconciliation"])

    def test_venv_home_ignores_the_plugin_scoped_claude_variable(self) -> None:
        # Inside the memory plugin CLAUDE_PLUGIN_DATA points at *memory's*
        # data dir, not the sibling indexkit dir where its hook built the
        # venv, so inheriting it would resolve the wrong runtime.
        with patch.dict(
            os.environ, {"CLAUDE_PLUGIN_DATA": "/tmp/memory-plugin-data"}, clear=True
        ):
            resolved = memory_provider._indexkit_home()
        self.assertNotIn("memory-plugin-data", str(resolved))
        with patch.dict(
            os.environ, {"CONTEXT_KIT_INDEXKIT_HOME": "/tmp/explicit"}, clear=True
        ):
            self.assertEqual("/tmp/explicit", str(memory_provider._indexkit_home()))

    def test_venv_home_resolves_the_sibling_plugin_not_our_own_data(self) -> None:
        # CLAUDE_PLUGIN_DATA is plugin-scoped, so reading it naively yields
        # *memory's* data dir. Both hosts lay plugin data out as
        # `<root>/<plugin>`, so indexkit's home is a sibling of ours —
        # verified against a real Copilot install at
        # ~/.copilot/plugin-data/context-kit/{memory,indexkit}.
        root = self.root / "plugin-data" / "context-kit"
        (root / "indexkit" / "venv").mkdir(parents=True)
        (root / "memory").mkdir(parents=True)
        with patch.dict(
            os.environ, {"CLAUDE_PLUGIN_DATA": str(root / "memory")}, clear=True
        ):
            resolved = memory_provider._indexkit_home()
        self.assertEqual(root / "indexkit", resolved)

    def test_venv_home_falls_back_when_no_sibling_exists(self) -> None:
        # A guess that does not exist must degrade to the documented default
        # rather than pointing the launcher at an empty directory.
        with patch.dict(
            os.environ,
            {"CLAUDE_PLUGIN_DATA": str(self.root / "absent" / "memory")},
            clear=True,
        ):
            resolved = memory_provider._indexkit_home()
        self.assertNotIn("absent", str(resolved))
        with patch.dict(
            os.environ, {"CONTEXT_KIT_INDEXKIT_HOME": "/tmp/explicit"}, clear=True
        ):
            self.assertEqual("/tmp/explicit", str(memory_provider._indexkit_home()))

    def test_wake_builds_a_digest_without_invoking_rag(self) -> None:
        # The digest reads local records, which are the system of record, so
        # it is identical across providers and never shells out.
        executable = self.fake_rag()
        self.capture_and_sync(executable)
        before = len(self.recorded_calls())
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["wake", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual("rag", payload["provider"])
        self.assertEqual(["retry-policy"], [m["id"] for m in payload["memories"]])
        self.assertTrue(payload["reconciled"])
        self.assertIn("retry", payload["context"])
        self.assertEqual(before, len(self.recorded_calls()))

    # ------------------------------------------------------------------
    # runtime bootstrap (the Copilot/APM gap)
    # ------------------------------------------------------------------

    def test_runtime_gate_is_skipped_for_a_user_supplied_executable(self) -> None:
        # CONTEXT_KIT_INDEXKIT_BIN points at an executable that manages its own
        # runtime, so the bundled venv is irrelevant and must not be gated on.
        executable = self.fake_rag()
        with patch.dict(os.environ, self.env(executable), clear=True):
            result, stdout, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        self.assertNotIn("runtime", json.loads(stdout))

    def test_doctor_refuses_with_an_actionable_command_when_runtime_is_missing(
        self,
    ) -> None:
        bundled = self.root / "bundled-rag"
        bundled.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        bundled.chmod(0o700)
        with (
            patch.dict(
                os.environ, {"CONTEXT_KIT_INDEXKIT_BIN": str(bundled)}, clear=True
            ),
            patch.object(memory_provider, "_bundled_executable", return_value=bundled),
            patch.object(
                memory_provider,
                "_rag_runtime_status",
                return_value={
                    "status": "missing",
                    "detail": "no interpreter at /tmp/venv/bin/python",
                    "bootstrap_command": "bash /plugins/indexkit/scripts/bootstrap.sh",
                },
            ),
        ):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(2, result)
        # The refusal must carry the exact command, and say why the host
        # did not do it automatically.
        self.assertIn("bash /plugins/indexkit/scripts/bootstrap.sh", stderr)
        self.assertIn("APM does not deploy", stderr)

    def test_doctor_refuses_on_a_stale_runtime(self) -> None:
        # A venv built from different project metadata runs stale code
        # silently; it must be treated as loudly as a missing one.
        bundled = self.root / "bundled-rag"
        bundled.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        bundled.chmod(0o700)
        with (
            patch.dict(
                os.environ, {"CONTEXT_KIT_INDEXKIT_BIN": str(bundled)}, clear=True
            ),
            patch.object(memory_provider, "_bundled_executable", return_value=bundled),
            patch.object(
                memory_provider,
                "_rag_runtime_status",
                return_value={
                    "status": "stale",
                    "detail": "venv was built from different pyproject.toml metadata",
                    "bootstrap_command": "bash bootstrap.sh",
                },
            ),
        ):
            result, _, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(2, result)
        self.assertIn("stale", stderr)

    def test_doctor_passes_the_bootstrap_flag_through(self) -> None:
        executable = self.fake_rag()
        seen: dict[str, object] = {}

        def fake_status(*, bootstrap: bool = False) -> dict[str, object]:
            seen["bootstrap"] = bootstrap
            return {"status": "ready", "venv": "/tmp/venv"}

        with (
            patch.dict(os.environ, self.env(executable), clear=True),
            patch.object(
                memory_provider, "_bundled_executable", return_value=executable
            ),
            patch.object(memory_provider, "_rag_runtime_status", fake_status),
        ):
            result, stdout, stderr = self.invoke(
                ["doctor", "--provider", "rag", "--bootstrap", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        self.assertIs(True, seen["bootstrap"])
        self.assertEqual("ready", json.loads(stdout)["runtime"]["status"])

    def test_unknown_runtime_does_not_block(self) -> None:
        # If indexkit is not installed as a sibling the check cannot answer;
        # that must not become a hard refusal for an otherwise working CLI.
        executable = self.fake_rag()
        with (
            patch.dict(os.environ, self.env(executable), clear=True),
            patch.object(
                memory_provider, "_bundled_executable", return_value=executable
            ),
            patch.object(
                memory_provider,
                "_rag_runtime_status",
                return_value={"status": "unknown", "detail": "not found"},
            ),
        ):
            result, stdout, stderr = self.invoke(
                ["doctor", "--provider", "rag", *self.base_args()]
            )
        self.assertEqual(0, result, stderr)
        self.assertEqual("ready", json.loads(stdout)["status"])


class RagBootstrapCheckTests(unittest.TestCase):
    """`bootstrap.sh --check` is the host-neutral readiness contract."""

    SCRIPT = PLUGIN_ROOT.parent / "indexkit" / "scripts" / "bootstrap.sh"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / "rag-home"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def check(self, *, path: str | None = None) -> tuple[int, dict[str, str]]:
        import subprocess

        env = dict(os.environ, CONTEXT_KIT_INDEXKIT_HOME=str(self.home))
        if path is not None:
            env["PATH"] = path
        result = subprocess.run(
            ["bash", str(self.SCRIPT), "--check"],
            capture_output=True,
            check=False,
            timeout=60,
            env=env,
        )
        report = {}
        for line in result.stdout.decode().splitlines():
            key, sep, value = line.partition("=")
            if sep:
                report[key] = value
        return result.returncode, report

    def test_reports_missing_without_creating_anything(self) -> None:
        code, report = self.check()
        self.assertEqual(3, code)
        # `venv_status` is the raw state and stays accurate whether or not uv
        # is installed; `status` folds in "you cannot rebuild it yet".
        self.assertEqual("missing", report["venv_status"])
        self.assertIn(report["status"], {"missing", "uv-missing"})
        self.assertIn("bootstrap.sh", report["bootstrap_command"])
        # A readiness check must not have side effects.
        self.assertFalse(self.home.exists())

    def test_a_usable_venv_is_ready_even_without_uv(self) -> None:
        # uv only builds the venv. Reporting "uv-missing" for a runtime that
        # already works would send the user chasing an irrelevant install.
        (self.home / "venv" / "bin").mkdir(parents=True)
        interpreter = self.home / "venv" / "bin" / "python"
        interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
        interpreter.chmod(0o700)
        project = self.SCRIPT.parents[1] / "pyproject.toml"
        digest = hashlib.sha256(project.read_bytes()).hexdigest()
        (self.home / "pyproject.sha").write_text(digest + "\n", encoding="utf-8")

        code, report = self.check(path="/usr/bin:/bin")
        self.assertEqual(0, code)
        self.assertEqual("ready", report["status"])
        self.assertEqual("missing", report["uv"])

    def test_reports_stale_when_the_stamp_does_not_match(self) -> None:
        (self.home / "venv" / "bin").mkdir(parents=True)
        interpreter = self.home / "venv" / "bin" / "python"
        interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
        interpreter.chmod(0o700)
        (self.home / "pyproject.sha").write_text(
            "not-the-current-sha\n", encoding="utf-8"
        )

        code, report = self.check()
        self.assertEqual(3, code)
        self.assertEqual("stale", report["venv_status"])
        self.assertIn(report["status"], {"stale", "uv-missing"})

    def test_rejects_an_unknown_flag(self) -> None:
        import subprocess

        result = subprocess.run(
            ["bash", str(self.SCRIPT), "--nope"],
            capture_output=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, result.returncode)


if __name__ == "__main__":
    unittest.main()
