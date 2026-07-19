from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN_ROOT / "scripts" / "run-evidence-command.py"
SPEC = importlib.util.spec_from_file_location("run_evidence_command", RUNNER)
assert SPEC is not None and SPEC.loader is not None
run_evidence_command = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_evidence_command)


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

    def test_refuses_non_posix_platform(self) -> None:
        with self.assertRaisesRegex(
            run_evidence_command.Refusal,
            "requires a POSIX platform",
        ):
            run_evidence_command._validate_platform("nt")

    def test_main_returns_structured_refusal_for_unsupported_platform(self) -> None:
        refusal = run_evidence_command.Refusal("unsupported platform")
        with (
            patch.object(
                run_evidence_command,
                "_validate_platform",
                side_effect=refusal,
            ),
            patch("builtins.print") as print_mock,
        ):
            result = run_evidence_command.main(
                [
                    "--command-id",
                    "approved",
                    "--claim",
                    "claim",
                    "--environment-label",
                    "test",
                    "--cwd",
                    str(self.root),
                    "--run-id",
                    "unsupported-platform",
                ]
            )

        self.assertEqual(2, result)
        self.assertIn('"status": "refused"', print_mock.call_args.args[0])
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

    def test_timeout_still_applies_after_child_closes_output_streams(self) -> None:
        self.write_config(
            {
                "closes-streams": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import os, time; os.close(1); os.close(2); time.sleep(2)",
                    ],
                    "timeout_seconds": 0.05,
                    "max_output_bytes": 1024,
                }
            }
        )

        started = time.monotonic()
        result = self.run_command("closes-streams")
        elapsed = time.monotonic() - started
        report = self.report()

        self.assertLess(elapsed, 1.0)
        self.assertEqual(result.returncode, 124)
        self.assertEqual(report["observations"]["termination_reason"], "timeout")
        self.assertIn(
            report["cleanup_status"], {"process-group-killed", "process-killed"}
        )

    @unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
    def test_timeout_kills_descendant_group_after_direct_child_exits(self) -> None:
        self.write_config(
            {
                "spawns-descendant": {
                    "argv": [
                        sys.executable,
                        "-c",
                        (
                            "import subprocess, sys; "
                            "subprocess.Popen([sys.executable, '-c', "
                            "'import time; time.sleep(2)'])"
                        ),
                    ],
                    "timeout_seconds": 0.05,
                    "max_output_bytes": 1024,
                }
            }
        )

        started = time.monotonic()
        result = self.run_command("spawns-descendant")
        elapsed = time.monotonic() - started
        report = self.report()

        self.assertLess(elapsed, 1.0)
        self.assertEqual(result.returncode, 124)
        self.assertEqual(report["observations"]["termination_reason"], "timeout")
        self.assertEqual(report["cleanup_status"], "process-group-killed")

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
