from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN_ROOT / "scripts" / "run-evidence-command.py"


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = self.root / "commands.json"
        self.artifacts = self.root / "artifacts"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_config(self, commands: dict[str, dict[str, object]]) -> None:
        self.config.write_text(
            json.dumps({"version": 1, "commands": commands}),
            encoding="utf-8",
        )

    def run_command(
        self, command_id: str, run_id: str = "test-run"
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--config",
                str(self.config),
                "--command-id",
                command_id,
                "--claim",
                "The runtime behaves as expected",
                "--environment-label",
                "unit-test",
                "--cwd",
                str(self.root),
                "--artifact-dir",
                str(self.artifacts),
                "--run-id",
                run_id,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def report(self, run_id: str = "test-run") -> dict[str, object]:
        return json.loads((self.artifacts / f"{run_id}.json").read_text())

    def test_refuses_command_not_in_allowlist(self) -> None:
        self.write_config(
            {
                "approved": {
                    "argv": [sys.executable, "-c", "print('ok')"],
                    "timeout_seconds": 2,
                    "max_output_bytes": 1024,
                }
            }
        )

        result = self.run_command("unapproved")

        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowlisted", result.stderr)
        self.assertFalse(self.artifacts.exists())

    def test_propagates_nonzero_child_exit(self) -> None:
        self.write_config(
            {
                "fails": {
                    "argv": [sys.executable, "-c", "raise SystemExit(7)"],
                    "timeout_seconds": 2,
                    "max_output_bytes": 1024,
                }
            }
        )

        result = self.run_command("fails")

        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.report()["observations"]["exit_code"], 7)
        self.assertEqual(
            self.report()["observations"]["termination_reason"],
            "child-nonzero",
        )

    def test_timeout_is_reported_and_process_is_terminated(self) -> None:
        self.write_config(
            {
                "slow": {
                    "argv": [sys.executable, "-c", "import time; time.sleep(2)"],
                    "timeout_seconds": 0.05,
                    "max_output_bytes": 1024,
                }
            }
        )

        result = self.run_command("slow")
        report = self.report()

        self.assertEqual(result.returncode, 124)
        self.assertEqual(report["observations"]["termination_reason"], "timeout")
        self.assertIn(
            report["cleanup_status"], {"process-group-killed", "process-killed"}
        )

    def test_output_limit_caps_artifact_and_terminates(self) -> None:
        self.write_config(
            {
                "noisy": {
                    "argv": [sys.executable, "-c", "print('x' * 4096)"],
                    "timeout_seconds": 2,
                    "max_output_bytes": 64,
                }
            }
        )

        result = self.run_command("noisy")
        report = self.report()

        self.assertEqual(result.returncode, 125)
        self.assertEqual((self.artifacts / "test-run.stdout").stat().st_size, 64)
        self.assertTrue(report["observations"]["stdout_truncated"])
        self.assertEqual(
            report["observations"]["termination_reason"],
            "output-limit",
        )

    def test_success_writes_verdict_ready_artifacts(self) -> None:
        self.write_config(
            {
                "passes": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys; print('observed'); print('note', file=sys.stderr)",
                    ],
                    "timeout_seconds": 2,
                    "max_output_bytes": 1024,
                }
            }
        )

        result = self.run_command("passes")
        report = self.report()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["reproduction_command_id"], "passes")
        self.assertEqual(report["environment"]["cwd"], str(self.root.resolve()))
        self.assertEqual(report["observations"]["stdout_excerpt"], "observed\n")
        self.assertEqual(report["observations"]["stderr_excerpt"], "note\n")
        self.assertEqual(report["cleanup_status"], "not-needed")
        self.assertTrue((self.artifacts / "test-run.stdout").is_file())
        self.assertTrue((self.artifacts / "test-run.stderr").is_file())


if __name__ == "__main__":
    unittest.main()
