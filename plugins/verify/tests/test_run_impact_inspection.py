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

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN_ROOT / "scripts" / "run-impact-inspection.py"
SPEC = importlib.util.spec_from_file_location("run_impact_inspection", RUNNER)
assert SPEC is not None and SPEC.loader is not None
run_impact_inspection = importlib.util.module_from_spec(SPEC)
# Register before exec so dataclass() can resolve the module for its type checks.
sys.modules[SPEC.name] = run_impact_inspection
SPEC.loader.exec_module(run_impact_inspection)


def _has_git() -> bool:
    import shutil

    return shutil.which("git") is not None


def _has_jq() -> bool:
    import shutil

    return shutil.which("jq") is not None


class RunnerCliTests(unittest.TestCase):
    """Exercise the runner as a subprocess, the way an agent invokes it."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_runner(
        self, *cli_args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *cli_args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(self.root),
            env=self.git_env(),
            check=True,
            capture_output=True,
        )

    def git_env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "HOME": str(self.root),
        }

    def init_repo(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        (self.root / "tracked.txt").write_text("alpha needle beta\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-q", "-m", "seed commit")

    # --- Discovery -----------------------------------------------------------

    def test_list_emits_operation_catalog(self) -> None:
        result = self.run_runner("--list")
        self.assertEqual(result.returncode, 0)
        catalog = json.loads(result.stdout)
        ids = {operation["id"] for operation in catalog["operations"]}
        self.assertIn("git-log-path", ids)
        self.assertIn("json-field", ids)
        self.assertIn("yaml-keys", ids)
        self.assertIn("adr-explain-path", ids)
        modalities = {operation["modality"] for operation in catalog["operations"]}
        self.assertLessEqual({"history", "structured-data", "governance"}, modalities)

    # --- Refusals ------------------------------------------------------------

    def test_unknown_operation_is_refused(self) -> None:
        result = self.run_runner(
            "--operation", "git-force-push", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["status"], "refused")
        self.assertIn("not enforceable", payload["error"])

    def test_missing_operation_is_refused(self) -> None:
        result = self.run_runner("--root", str(self.root))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["status"], "refused")

    def test_missing_root_is_refused(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "CONTEXT_KIT_IMPACT_ROOT"}
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--operation", "git-log-recent"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("root", json.loads(result.stderr)["error"])

    def test_relative_root_is_refused(self) -> None:
        result = self.run_runner("--operation", "git-log-recent", "--root", ".")
        self.assertEqual(result.returncode, 2)
        self.assertIn("absolute", json.loads(result.stderr)["error"])

    def test_missing_required_parameter_is_refused(self) -> None:
        result = self.run_runner(
            "--operation", "git-log-path", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires parameter", json.loads(result.stderr)["error"])

    def test_unknown_parameter_is_refused(self) -> None:
        result = self.run_runner(
            "--operation",
            "git-log-recent",
            "--root",
            str(self.root),
            "--param",
            "path=x",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not accept", json.loads(result.stderr)["error"])

    def test_malformed_parameter_is_refused(self) -> None:
        result = self.run_runner(
            "--operation",
            "git-log-recent",
            "--root",
            str(self.root),
            "--param",
            "max_count",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("name=value", json.loads(result.stderr)["error"])

    # --- Mutation / exec vector rejection -----------------------------------

    def test_output_write_flag_cannot_reach_a_revision_slot(self) -> None:
        # The named git write vector as a revision value is rejected before spawn.
        result = self.run_runner(
            "--operation",
            "git-show-commit",
            "--root",
            str(self.root),
            "--param",
            "rev=--output=escape.txt",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("revision", json.loads(result.stderr)["error"])
        self.assertFalse((self.root / "escape.txt").exists())

    def test_pager_exec_flag_cannot_reach_a_field_slot(self) -> None:
        result = self.run_runner(
            "--operation",
            "json-field",
            "--root",
            str(self.root),
            "--param",
            "path=data.json",
            "--param",
            "field=--open-files-in-pager=touch pwned",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("field", json.loads(result.stderr)["error"])

    def test_inplace_flag_cannot_reach_a_path_slot(self) -> None:
        result = self.run_runner(
            "--operation",
            "json-keys",
            "--root",
            str(self.root),
            "--param",
            "path=-i",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("dash", json.loads(result.stderr)["error"])

    def test_field_rejects_raw_expression(self) -> None:
        result = self.run_runner(
            "--operation",
            "json-field",
            "--root",
            str(self.root),
            "--param",
            "path=data.json",
            "--param",
            "field=. | keys",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("field", json.loads(result.stderr)["error"])

    # --- Path containment ----------------------------------------------------

    def test_absolute_path_is_refused(self) -> None:
        result = self.run_runner(
            "--operation",
            "json-keys",
            "--root",
            str(self.root),
            "--param",
            "path=/etc/hosts",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("relative", json.loads(result.stderr)["error"])

    def test_dotdot_path_escape_is_refused(self) -> None:
        result = self.run_runner(
            "--operation",
            "json-keys",
            "--root",
            str(self.root),
            "--param",
            "path=../secret.json",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("escapes", json.loads(result.stderr)["error"])

    def test_symlink_escaping_root_is_refused(self) -> None:
        outside = Path(self.temp_dir.name).parent / "outside-target.json"
        outside.write_text("{}", encoding="utf-8")
        try:
            link = self.root / "link.json"
            os.symlink(outside, link)
            result = self.run_runner(
                "--operation",
                "json-keys",
                "--root",
                str(self.root),
                "--param",
                "path=link.json",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("escapes", json.loads(result.stderr)["error"])
        finally:
            outside.unlink(missing_ok=True)

    # --- Unavailable, never a silent downgrade ------------------------------

    def test_missing_tool_reports_unavailable(self) -> None:
        # main() resolves availability with shutil.which(command[0]), which
        # consults the runner process's own PATH. Point that PATH at a directory
        # that cannot exist, so the tool is unresolvable whether or not yq (or
        # anything else) is installed on the host -- CI ships yq, this box does
        # not, and both must exercise the unavailable path deterministically.
        env = {**os.environ, "PATH": str(self.root / "no-such-bin-dir")}
        result = self.run_runner(
            "--operation",
            "yaml-keys",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("yq", payload["error"])
        self.assertIn("operations_hint", payload)

    # --- Successful execution ------------------------------------------------

    @unittest.skipUnless(_has_git(), "requires git")
    def test_git_log_path_executes_read_only(self) -> None:
        self.init_repo()
        result = self.run_runner(
            "--operation",
            "git-log-path",
            "--root",
            str(self.root),
            "--param",
            "path=tracked.txt",
            "--param",
            "max_count=5",
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "executed")
        self.assertEqual(report["operation"], "git-log-path")
        self.assertIn("--no-pager", report["argv"])
        self.assertIn("seed commit", report["observations"]["stdout_excerpt"])

    @unittest.skipUnless(_has_git(), "requires git")
    def test_git_grep_finds_tracked_content(self) -> None:
        self.init_repo()
        result = self.run_runner(
            "--operation",
            "git-grep",
            "--root",
            str(self.root),
            "--param",
            "pattern=needle",
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertIn("--basic-regexp", report["argv"])
        self.assertIn("needle", report["observations"]["stdout_excerpt"])

    @unittest.skipUnless(_has_git(), "requires git")
    def test_repo_local_diff_external_is_neutralized(self) -> None:
        self.init_repo()
        marker = self.root / "diff-external-ran.marker"
        # A program-executing setting in the analysis root's own .git/config that
        # environment scrubbing does not cover: diff.external runs for `git diff`.
        self.git("config", "diff.external", f"touch {marker}")
        (self.root / "tracked.txt").write_text(
            "alpha needle beta gamma\n", encoding="utf-8"
        )
        self.git("commit", "-q", "-am", "second commit")

        # Control: plain git (no runner hardening) does execute the setting, so the
        # vector is real. Delete the marker before exercising the runner.
        subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            cwd=str(self.root),
            env=self.git_env(),
            check=False,
            capture_output=True,
        )
        self.assertTrue(marker.exists(), "control: repo-local diff.external should run")
        marker.unlink()

        result = self.run_runner(
            "--operation",
            "git-diff-revs",
            "--root",
            str(self.root),
            "--param",
            "base=HEAD~1",
            "--param",
            "head=HEAD",
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(
            marker.exists(),
            "runner-owned -c overrides must neutralize repo-local diff.external",
        )

    # --- Field filter is a bracket key, not a bare dotted expression --------

    @unittest.skipUnless(_has_jq(), "requires jq")
    def test_json_field_addresses_nested_key(self) -> None:
        # Split out of the git-hardening test above: the runner must build a
        # bracket filter so the jq assertion fails only for a field-encoding
        # reason, and the test stays runnable on a host with git but without jq.
        (self.root / "data.json").write_text(
            json.dumps({"outer": {"inner": "found"}}), encoding="utf-8"
        )
        result = self.run_runner(
            "--operation",
            "json-field",
            "--root",
            str(self.root),
            "--param",
            "path=data.json",
            "--param",
            "field=outer.inner",
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["argv"], ["jq", '.["outer"]["inner"]', "data.json"])
        self.assertIn("found", report["observations"]["stdout_excerpt"])

    @unittest.skipUnless(_has_jq(), "requires jq")
    def test_json_field_hyphenated_key_addresses_literal_key(self) -> None:
        # A bare `.release-name` filter parses as subtraction and returns the
        # wrong thing; the bracket form must address the literal key.
        (self.root / "data.json").write_text(
            json.dumps({"release-name": {"inner": "found"}}), encoding="utf-8"
        )
        result = self.run_runner(
            "--operation",
            "json-field",
            "--root",
            str(self.root),
            "--param",
            "path=data.json",
            "--param",
            "field=release-name.inner",
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(
            report["argv"], ["jq", '.["release-name"]["inner"]', "data.json"]
        )
        self.assertIn("found", report["observations"]["stdout_excerpt"])

    @unittest.skipUnless(_has_jq(), "requires jq")
    def test_json_field_digit_leading_key_addresses_literal_key(self) -> None:
        # A bare `.2fa` filter is a jq syntax error even though the regex accepts
        # the segment; the bracket form must address the literal key instead.
        (self.root / "data.json").write_text(
            json.dumps({"2fa": "enabled"}), encoding="utf-8"
        )
        result = self.run_runner(
            "--operation",
            "json-field",
            "--root",
            str(self.root),
            "--param",
            "path=data.json",
            "--param",
            "field=2fa",
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["argv"], ["jq", '.["2fa"]', "data.json"])
        self.assertIn("enabled", report["observations"]["stdout_excerpt"])

    @unittest.skipUnless(_has_git(), "requires git")
    def test_environment_is_scrubbed_of_redirection_vars(self) -> None:
        self.init_repo()
        # A poisoned GIT_DIR in the parent environment must not redirect the child.
        env = dict(os.environ)
        env["GIT_DIR"] = "/nonexistent/git/dir"
        env["GIT_EXTERNAL_DIFF"] = "touch pwned"
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--operation",
                "git-log-recent",
                "--root",
                str(self.root),
                "--param",
                "max_count=1",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertIn("seed commit", report["observations"]["stdout_excerpt"])
        self.assertNotIn("GIT_DIR", report["environment"]["keys"])
        self.assertNotIn("GIT_EXTERNAL_DIFF", report["environment"]["keys"])
        self.assertEqual(
            report["environment"]["keys"], sorted(report["environment"]["keys"])
        )

    # --- Bounded capture -----------------------------------------------------

    @unittest.skipUnless(_has_git(), "requires git")
    def test_output_cap_truncates_and_terminates(self) -> None:
        self.init_repo()
        big = "x needle " * 4000
        (self.root / "big.txt").write_text(big + "\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "big.txt"],
            cwd=str(self.root),
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "HOME": str(self.root),
            },
            check=True,
            capture_output=True,
        )
        result = self.run_runner(
            "--operation",
            "git-grep",
            "--root",
            str(self.root),
            "--param",
            "pattern=needle",
            "--max-output-bytes",
            "64",
        )
        self.assertEqual(result.returncode, 125)
        report = json.loads(result.stdout)
        self.assertTrue(report["observations"]["stdout_truncated"])
        self.assertLessEqual(report["observations"]["stdout_bytes"], 64)
        self.assertEqual(report["observations"]["termination_reason"], "output-limit")


class RunnerUnitTests(unittest.TestCase):
    """Directly exercise the validation and timeout internals."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validate_count_bounds(self) -> None:
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._validate_count("0")
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._validate_count("notanumber")
        self.assertEqual(run_impact_inspection._validate_count("7"), "7")

    def test_validate_platform_refuses_non_posix(self) -> None:
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._validate_platform("nt")
        self.assertIsNone(run_impact_inspection._validate_platform("posix"))

    def test_validate_rev_rejects_leading_dash(self) -> None:
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._validate_rev("-C/tmp")
        self.assertEqual(run_impact_inspection._validate_rev("HEAD~2"), "HEAD~2")

    def test_validate_field_builds_filter(self) -> None:
        self.assertEqual(
            run_impact_inspection._validate_field("a.b.c"),
            '.["a"]["b"]["c"]',
        )
        # A hyphenated segment and a digit-leading segment are both accepted by
        # the regex; each must encode to a literal bracket key, not a jq/yq
        # expression that would subtract or fail to parse.
        self.assertEqual(
            run_impact_inspection._validate_field("release-name"),
            '.["release-name"]',
        )
        self.assertEqual(
            run_impact_inspection._validate_field("2fa"),
            '.["2fa"]',
        )
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._validate_field("a.b; system")

    def test_clamp_ceils_and_defaults(self) -> None:
        self.assertEqual(
            run_impact_inspection._clamp(None, 30.0, 120.0, "t"),
            30.0,
        )
        self.assertEqual(
            run_impact_inspection._clamp(9999.0, 30.0, 120.0, "t"),
            120.0,
        )
        with self.assertRaises(run_impact_inspection.Refusal):
            run_impact_inspection._clamp(-1.0, 30.0, 120.0, "t")

    def test_timeout_terminates_a_slow_child(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        started = time.monotonic()
        _captured, _truncated, reason, cleanup, exit_code = (
            run_impact_inspection._capture(process, 0.1, 1024)
        )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0)
        self.assertEqual(reason, "timeout")
        self.assertEqual(exit_code, 124)
        self.assertIn(cleanup, {"process-group-killed", "process-killed"})


class GovernanceOperationTests(unittest.TestCase):
    """adrkit-backed governance operations (ADR-0003).

    Deliberately not a subclass of RunnerCliTests: inheriting a TestCase re-runs
    every inherited test method, so the harness is duplicated instead.

    adrkit is optional and contributor-side, so the behavior that matters most is
    the one when it is absent -- an unreached modality, never a silent skip and
    never a hard failure of the whole inspection.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        # Give the root a corpus by default. The `requires_dir` preflight runs
        # before the tool is resolved, so a corpus-less root short-circuits every
        # test here into the missing-corpus branch -- which is how the original
        # missing-tool test passed without ever reaching the code it named
        # ("adr" is a substring of "docs/adr"). Tests wanting the corpus-less
        # behavior build their own root.
        (self.root / "docs" / "adr").mkdir(parents=True)

    def corpusless_root(self) -> Path:
        extra = tempfile.TemporaryDirectory()
        self.addCleanup(extra.cleanup)
        return Path(extra.name).resolve()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_runner(
        self, *cli_args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *cli_args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_governance_catalog_is_exactly_the_read_only_verbs(self) -> None:
        # Substring checks on the operation *id* prove nothing: renaming an id
        # while pointing its builder at `adr new` would still pass. Assert the
        # exact id set, and inspect what each registered builder actually
        # produces, so the read-only guarantee is regression-tested at the argv
        # level where it is enforced.
        ops = {
            op.id: op
            for op in run_impact_inspection.OPERATIONS
            if op.modality == "governance"
        }
        self.assertEqual({"adr-explain-path", "adr-check-path"}, set(ops))

        readonly_verbs = {"explain", "check"}
        for op_id, op in ops.items():
            with self.subTest(operation=op_id):
                argv = op.build({"path": "some/file.py", "dir": "docs/adr"})
                self.assertEqual("adr", argv[0], "must invoke adrkit itself")
                self.assertIn(
                    argv[1],
                    readonly_verbs,
                    f"{op_id} invokes `adr {argv[1]}`, which is not a read-only verb",
                )
                # Nothing in the argv may name a writing verb in any position.
                self.assertFalse(
                    {"new", "migrate", "queue"} & set(argv),
                    f"{op_id} argv contains a writing verb: {argv}",
                )

    def test_missing_adr_reports_unavailable(self) -> None:
        # adrkit is Node-based and optional, so most machines running this suite
        # will not have it. Point PATH at a directory that cannot exist so the
        # unavailable path is exercised deterministically either way.
        env = {**os.environ, "PATH": str(self.root / "no-such-bin-dir")}
        env.pop("CONTEXT_KIT_ADR_BIN", None)
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["status"], "unavailable")
        # Assert the missing-*tool* wording specifically. Checking for "adr"
        # alone also matches the missing-corpus message via "docs/adr", so a
        # substring check cannot tell the two unavailable branches apart.
        self.assertIn("is not installed", payload["error"])

    def test_unavailable_names_a_remedy(self) -> None:
        # An unreached modality is the correct result, but an inert one: this
        # repository documents adrkit through `npx`, which leaves no `adr` on
        # PATH, so every contributor following the documentation got `unavailable`
        # forever with nothing telling them how to fix it. The payload must name
        # both remedies, or the failure stays invisible.
        env = {**os.environ, "PATH": str(self.root / "no-such-bin-dir")}
        env.pop("CONTEXT_KIT_ADR_BIN", None)
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 3)
        error = json.loads(result.stderr)["error"]
        self.assertIn("@adrkit/cli", error)
        self.assertIn("CONTEXT_KIT_ADR_BIN", error)

    def test_bin_override_runs_the_named_executable(self) -> None:
        # The reachability fix: an operator whose install is not a bare `adr` on
        # PATH names it explicitly. A stub stands in for adrkit so the test does
        # not require Node -- what is under test is the runner's resolution, not
        # adrkit's behavior.
        stub = self.root / "adr-stub"
        stub.write_text("#!/bin/sh\necho stub-ran\n")
        stub.chmod(0o755)
        env = {
            **os.environ,
            "PATH": str(self.root / "no-such-bin-dir"),
            "CONTEXT_KIT_ADR_BIN": str(stub),
        }
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "executed")
        # The audit record must name the binary that actually ran, and the rest
        # of the argv must be untouched by the override.
        self.assertEqual(str(stub.resolve()), report["argv"][0])
        self.assertEqual(
            ["explain", "apm.yml", "--dir", "docs/adr", "--json"], report["argv"][1:]
        )
        self.assertIn("stub-ran", report["observations"]["stdout_excerpt"])

    def test_unusable_bin_override_refuses_instead_of_falling_back(self) -> None:
        # Silently falling back to PATH would run a different binary than the
        # operator named and hide the misconfiguration -- the exact silent
        # downgrade this runner exists to prevent.
        env = {**os.environ, "CONTEXT_KIT_ADR_BIN": str(self.root / "not-here")}
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["status"], "refused")
        self.assertIn("CONTEXT_KIT_ADR_BIN", payload["error"])

    def test_blank_bin_override_refuses_rather_than_falling_through(self) -> None:
        # An absent variable and one set to nothing are different states. Reading
        # a blank value as "unset" would resolve a *different* binary than the
        # operator configured, which is the looks-honored-but-isn't failure this
        # override exists to prevent. Whitespace-only is the same state as empty.
        for label, value in (("empty", ""), ("whitespace-only", "   ")):
            with self.subTest(value=label):
                env = {**os.environ, "CONTEXT_KIT_ADR_BIN": value}
                result = self.run_runner(
                    "--operation",
                    "adr-explain-path",
                    "--root",
                    str(self.root),
                    "--param",
                    "path=apm.yml",
                    env=env,
                )
                self.assertEqual(result.returncode, 2)
                payload = json.loads(result.stderr)
                self.assertEqual(payload["status"], "refused")
                self.assertIn("CONTEXT_KIT_ADR_BIN", payload["error"])
                # The remedy must distinguish this from a bad path, so an
                # operator is told to unset rather than to fix the value.
                self.assertIn("empty value", payload["error"])

    def test_non_executable_bin_override_refuses(self) -> None:
        target = self.root / "adr-not-executable"
        target.write_text("#!/bin/sh\n")
        target.chmod(0o644)
        env = {**os.environ, "CONTEXT_KIT_ADR_BIN": str(target)}
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("executable", json.loads(result.stderr)["error"])

    def test_bin_override_does_not_become_a_package_fetch(self) -> None:
        # The rejected design was an `npx` fallback. Guard the property that
        # replaced it: the override names something that must already exist, so a
        # bare package specifier is refused rather than fetched.
        env = {**os.environ, "CONTEXT_KIT_ADR_BIN": "@adrkit/cli@0.12.0"}
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["status"], "refused")

    def test_no_operation_shells_out_to_a_package_runner(self) -> None:
        # `npx`/`pnpm dlx`/`uvx` would each make a "read-only, offline" operation
        # perform network I/O and execute registry code. No builder may name one.
        fetchers = {"npx", "pnpm", "dlx", "uvx", "pipx", "bunx", "yarn"}
        for op in run_impact_inspection.OPERATIONS:
            with self.subTest(operation=op.id):
                argv = op.build(
                    {
                        "path": "some/file.py",
                        "dir": "docs/adr",
                        "field": "a",
                        "pattern": "x",
                        "max_count": "5",
                        "base": "HEAD~1",
                        "head": "HEAD",
                        "rev": "HEAD",
                    }
                )
                self.assertFalse(
                    fetchers & set(argv),
                    f"{op.id} argv invokes a package runner: {argv}",
                )

    def test_missing_corpus_reports_unavailable_not_refusal(self) -> None:
        # adrkit exits 2 when --dir is absent, and this runner reserves 2 for
        # policy refusal. Without a preflight the caller would read "no corpus
        # here" as "the runner refused", and an absent corpus would never yield
        # the unreached result the contract requires. Absence of a corpus is not
        # evidence that no decision governs the path.
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.corpusless_root()),  # a temp dir with no docs/adr
            "--param",
            "path=apm.yml",
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("docs/adr", payload["error"])

    def test_adr_corpus_dir_is_path_confined(self) -> None:
        # The corpus directory is caller-supplied, so it goes through the same
        # containment check as every other path parameter.
        result = self.run_runner(
            "--operation",
            "adr-explain-path",
            "--root",
            str(self.root),
            "--param",
            "path=apm.yml",
            "--param",
            "dir=../../etc",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("escapes", json.loads(result.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
