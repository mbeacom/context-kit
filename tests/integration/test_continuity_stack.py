from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_RUNNER = (
    REPOSITORY_ROOT
    / "plugins"
    / "runtime-evidence"
    / "scripts"
    / "run-evidence-command.py"
)
HANDOFF_VALIDATOR = (
    REPOSITORY_ROOT / "plugins" / "context-handoff" / "scripts" / "validate-handoff.py"
)
MEMORY_PROVIDER = (
    REPOSITORY_ROOT / "plugins" / "memory" / "scripts" / "memory-provider.py"
)
PROJECT = "mbeacom/context-kit"


@unittest.skipUnless(os.name == "posix", "runtime-evidence requires POSIX")
class ContinuityStackIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.memory_home = self.state / "memory"

        self.git("init")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.name", "Continuity Integration")
        self.git("config", "user.email", "continuity@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", f"https://github.com/{PROJECT}.git")
        (self.repo / "claim.txt").write_text(
            "continuity runtime contract\n",
            encoding="utf-8",
        )
        self.git("add", "claim.txt")
        self.git("commit", "-m", "Create runtime claim")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def run_script(
        self,
        script: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def current_handoff_arguments(self, head: str) -> list[str]:
        return [
            "--current-repository",
            PROJECT,
            "--current-branch",
            "main",
            "--current-base-ref",
            "main",
            "--current-head",
            head,
            "--current-base-commit",
            head,
            "--current-worktree-state",
            "clean",
        ]

    def write_handoff(
        self,
        report: dict[str, object],
        head: str,
    ) -> Path:
        pointers = report["artifact_output_pointers"]
        self.assertIsInstance(pointers, dict)
        report_path = pointers["report"]
        config_hash = pointers["config_sha256"]
        command_id = report["reproduction_command_id"]
        handoff = self.state / "handoff.md"

        # The plugins deliberately do not auto-ingest each other's artifacts.
        # This fixture models the documented human/agent compilation boundary.
        sections = {
            "Scope": "- Preserve verified continuity state without hidden ingestion.",
            "Verified Facts": (
                f"- Runtime command `{command_id}` observed repository HEAD `{head}`."
            ),
            "Decisions": (
                "- Treat runtime artifacts as evidence and the handoff as current "
                "task state."
            ),
            "Changed Files": "- None.",
            "Completed Work": "- Collected bounded runtime evidence.",
            "Unresolved Items": "- None.",
            "Next Steps": "1. Revalidate repository state before resuming.",
            "Validation State": (
                f"- passed - `{command_id}` - exact-ID allowlisted command exited 0."
            ),
            "Provenance and Freshness": "\n".join(
                [
                    f"- Runtime report: `{report_path}`.",
                    f"- Allowlist SHA-256: `{config_hash}`.",
                    f"- Compiled from `{PROJECT}` on `main` at `{head}`.",
                    "- Revalidate if HEAD, base, or worktree state changes.",
                ]
            ),
        }
        body = "\n\n".join(
            f"## {heading}\n\n{sections[heading]}"
            for heading in (
                "Scope",
                "Verified Facts",
                "Decisions",
                "Changed Files",
                "Completed Work",
                "Unresolved Items",
                "Next Steps",
                "Validation State",
                "Provenance and Freshness",
            )
        )
        handoff.write_text(
            "\n".join(
                [
                    "---",
                    "schema: context-kit/handoff-v1",
                    "generated_at: 2026-07-19T16:00:00-04:00",
                    f"repository: {PROJECT}",
                    f"worktree: {self.repo}",
                    "branch: main",
                    f"head: {head}",
                    "base_ref: main",
                    f"base_commit: {head}",
                    "worktree_state: clean",
                    "---",
                    "",
                    "# Context Handoff",
                    "",
                    body,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return handoff

    def write_reviewed_memory(self, source: Path, head: str) -> Path:
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        record = self.state / "reviewed-memory.md"
        record.write_text(
            "\n".join(
                [
                    "---",
                    "schema: context-kit/memory-v1",
                    "id: continuity-runtime-head",
                    "type: episode",
                    "scope: project",
                    f"repository: {PROJECT}",
                    "branch: main",
                    f"head: {head}",
                    "observed_at: 2026-07-19T16:00:00-04:00",
                    "captured_at: 2026-07-19T16:05:00-04:00",
                    "freshness: current",
                    "review: accepted",
                    f"source: {source}",
                    f"source_hash: {source_hash}",
                    "---",
                    "",
                    "## Primary Memory",
                    "",
                    f"Historical runtime evidence recorded repository HEAD {head}.",
                    "",
                    "## Cue Anchors",
                    "",
                    "- continuity runtime head",
                    "- historical handoff evidence",
                    "",
                    "## Evidence",
                    "",
                    f"- `{source}` - reviewed archived handoff.",
                    "",
                    "## Supersedes",
                    "",
                    "- None.",
                    "",
                    "## Review Notes",
                    "",
                    "- Accepted after validating and archiving the handoff.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return record

    def test_evidence_handoff_and_memory_preserve_authority_boundary(self) -> None:
        original_head = self.git("rev-parse", "HEAD")
        config = self.state / "runtime-commands.json"
        config.write_text(
            json.dumps(
                {
                    "version": 1,
                    "commands": {
                        "current-head": {
                            "argv": ["git", "rev-parse", "HEAD"],
                            "timeout_seconds": 5,
                            "max_output_bytes": 128,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        config.chmod(0o600)
        artifacts = self.state / "runtime-evidence"

        runtime = self.run_script(
            RUNTIME_RUNNER,
            "--config",
            str(config),
            "--command-id",
            "current-head",
            "--claim",
            "The repository HEAD can be observed at runtime.",
            "--environment-label",
            "continuity-integration",
            "--cwd",
            str(self.repo),
            "--artifact-dir",
            str(artifacts),
            "--run-id",
            "continuity",
        )
        self.assertEqual(0, runtime.returncode, runtime.stderr)
        report = json.loads(runtime.stdout)
        pointers = report["artifact_output_pointers"]
        report_path = Path(pointers["report"])
        stdout_path = Path(pointers["stdout"])
        stderr_path = Path(pointers["stderr"])
        resolved_artifacts = artifacts.resolve()
        self.assertEqual(resolved_artifacts / "continuity.json", report_path)
        self.assertEqual(resolved_artifacts / "continuity.stdout", stdout_path)
        self.assertEqual(resolved_artifacts / "continuity.stderr", stderr_path)
        self.assertTrue(report_path.is_file())
        self.assertTrue(stdout_path.is_file())
        self.assertTrue(stderr_path.is_file())
        self.assertEqual(
            report,
            json.loads(report_path.read_text(encoding="utf-8")),
        )
        self.assertEqual(
            f"{original_head}\n",
            report["observations"]["stdout_excerpt"],
        )
        self.assertEqual(f"{original_head}\n", stdout_path.read_text(encoding="utf-8"))
        self.assertEqual("", stderr_path.read_text(encoding="utf-8"))
        self.assertLessEqual(stdout_path.stat().st_size, 128)
        self.assertLessEqual(stderr_path.stat().st_size, 128)
        self.assertEqual("current-head", report["reproduction_command_id"])

        handoff = self.write_handoff(report, original_head)
        original_handoff = handoff.read_bytes()
        valid = self.run_script(
            HANDOFF_VALIDATOR,
            str(handoff),
            *self.current_handoff_arguments(original_head),
        )
        self.assertEqual(0, valid.returncode, valid.stderr)

        mismatch = self.run_script(
            HANDOFF_VALIDATOR,
            str(handoff),
            "--current-repository",
            "other/repository",
        )
        self.assertEqual(2, mismatch.returncode)
        self.assertIn("MISMATCH: repository mismatch", mismatch.stderr)

        archive = self.run_script(
            MEMORY_PROVIDER,
            "archive-handoff",
            str(handoff),
            "--repo",
            str(self.repo),
            "--provider",
            "none",
            "--home",
            str(self.memory_home),
            "--project",
            PROJECT,
        )
        self.assertEqual(0, archive.returncode, archive.stderr)
        archive_result = json.loads(archive.stdout)
        archived_handoff = Path(archive_result["artifact"])
        self.assertFalse(archive_result["provider_archived"])
        self.assertEqual(original_handoff, archived_handoff.read_bytes())

        record = self.write_reviewed_memory(archived_handoff, original_head)
        validated_memory = self.run_script(MEMORY_PROVIDER, "validate", str(record))
        self.assertEqual(0, validated_memory.returncode, validated_memory.stderr)
        capture = self.run_script(
            MEMORY_PROVIDER,
            "capture",
            str(record),
            "--provider",
            "none",
            "--home",
            str(self.memory_home),
            "--project",
            PROJECT,
        )
        self.assertEqual(0, capture.returncode, capture.stderr)
        self.assertFalse(json.loads(capture.stdout)["provider_archived"])

        recalled = self.run_script(
            MEMORY_PROVIDER,
            "search",
            "continuity runtime head",
            "--provider",
            "none",
            "--home",
            str(self.memory_home),
            "--project",
            PROJECT,
        )
        self.assertEqual(0, recalled.returncode, recalled.stderr)
        recalled_record = json.loads(recalled.stdout)["records"][0]
        self.assertEqual("accepted", recalled_record["review"])
        self.assertEqual("current", recalled_record["freshness"])
        self.assertEqual("verified", recalled_record["source_state"])
        self.assertEqual(str(archived_handoff), recalled_record["source"])

        (self.repo / "current-state.txt").write_text(
            "repository state is newer than the handoff\n",
            encoding="utf-8",
        )
        self.git("add", "current-state.txt")
        self.git("commit", "-m", "Advance repository state")
        current_head = self.git("rev-parse", "HEAD")
        self.assertNotEqual(original_head, current_head)

        stale = self.run_script(
            HANDOFF_VALIDATOR,
            str(handoff),
            *self.current_handoff_arguments(current_head),
        )
        self.assertEqual(3, stale.returncode)
        self.assertIn("STALE: head stale", stale.stderr)
        self.assertIn("STALE: base_commit stale", stale.stderr)

        recalled_after_change = self.run_script(
            MEMORY_PROVIDER,
            "search",
            "continuity runtime head",
            "--provider",
            "none",
            "--home",
            str(self.memory_home),
            "--project",
            PROJECT,
        )
        self.assertEqual(
            0,
            recalled_after_change.returncode,
            recalled_after_change.stderr,
        )
        remembered = json.loads(recalled_after_change.stdout)["records"][0]
        self.assertIn(original_head, remembered["primary_memory"])
        self.assertNotIn(current_head, remembered["primary_memory"])
        self.assertEqual(original_handoff, handoff.read_bytes())
        self.assertEqual(original_handoff, archived_handoff.read_bytes())


if __name__ == "__main__":
    unittest.main()
