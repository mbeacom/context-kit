from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "plugins/plugin-forge/scripts/version_bump.py"
SPEC = importlib.util.spec_from_file_location("version_bump", MODULE_PATH)
assert SPEC and SPEC.loader
version_bump = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = version_bump
SPEC.loader.exec_module(version_bump)


class VersionBumpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(self.repo),
            "GITHUB_BASE_REF": "",
        }
        self._git("init", "-b", "main")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        self._git("config", "commit.gpgsign", "false")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    # -- git helpers -----------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            shell=False,
            check=True,
            env=self.env,
        )

    def _commit(self, message: str) -> None:
        self._git("add", "-A")
        self._git("commit", "--no-gpg-sign", "-m", message)

    # -- plugin fixtures -------------------------------------------------

    def _write_plugin(self, name: str, version: str) -> Path:
        directory = self.repo / "plugins" / name
        manifest_path = directory / ".claude-plugin/plugin.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({"name": name, "version": version}), encoding="utf-8"
        )
        (directory / "apm.yml").write_text(
            f"name: {name}\nversion: {version}\n", encoding="utf-8"
        )
        (directory / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (directory / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (directory / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {version} — 2026-07-25\n\n- Release.\n",
            encoding="utf-8",
        )
        skill = directory / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"# {name}\n", encoding="utf-8")
        return directory

    def _set_version(self, name: str, version: str) -> None:
        directory = self.repo / "plugins" / name
        manifest_path = directory / ".claude-plugin/plugin.json"
        manifest_path.write_text(
            json.dumps({"name": name, "version": version}), encoding="utf-8"
        )
        (directory / "apm.yml").write_text(
            f"name: {name}\nversion: {version}\n", encoding="utf-8"
        )
        (directory / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {version} — 2026-07-25\n\n- Release.\n",
            encoding="utf-8",
        )

    def _touch(self, name: str, rel_path: str, content: str = "changed\n") -> None:
        path = self.repo / "plugins" / name / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _start_feature(self) -> None:
        """Diverge from main so merge-base(main, HEAD) is the base commit."""
        self._git("checkout", "-b", "work")

    def _check(self, base: str = "main") -> version_bump.VersionBumpResult:
        return version_bump.check_version_bumps(self.repo, base)

    # -- tests -----------------------------------------------------------

    def test_shipped_change_without_bump_fails(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# alpha edited\n")
        self._commit("edit skill")

        result = self._check()

        self.assertEqual([], result.notices)
        self.assertTrue(
            any(
                "plugin `alpha`: shipped content changed" in error
                and "skills/alpha/SKILL.md" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_shipped_change_with_bump_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# alpha edited\n")
        self._set_version("alpha", "1.0.1")
        self._commit("edit skill and bump")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertEqual(1, result.changed_plugins)

    def test_version_downgrade_fails(self) -> None:
        self._write_plugin("alpha", "2.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# alpha edited\n")
        self._set_version("alpha", "1.9.0")
        self._commit("downgrade")

        result = self._check()

        self.assertTrue(
            any(
                "did not increase (2.0.0 -> 1.9.0)" in error for error in result.errors
            ),
            result.errors,
        )

    def test_prerelease_to_release_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0-rc.1")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# alpha edited\n")
        self._set_version("alpha", "1.0.0")
        self._commit("promote")

        result = self._check()

        self.assertEqual([], result.errors)

    def test_docs_only_change_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "README.md", "# alpha docs\n")
        self._touch("alpha", "docs/guide.md", "# guide\n")
        self._commit("docs only")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertEqual(0, result.changed_plugins)

    def test_tests_only_change_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "tests/test_alpha.py", "assert True\n")
        self._commit("tests only")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertEqual(0, result.changed_plugins)

    def test_test_wrapper_script_change_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "scripts/test-alpha.sh", "echo hi\n")
        self._commit("test wrapper only")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertEqual(0, result.changed_plugins)

    def test_non_test_script_change_requires_bump(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "scripts/check-alpha.sh", "echo hi\n")
        self._commit("check script")

        result = self._check()

        self.assertTrue(
            any("scripts/check-alpha.sh" in error for error in result.errors),
            result.errors,
        )

    def test_new_plugin_is_skipped(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._write_plugin("beta", "0.1.0")
        self._commit("add beta")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertTrue(
            any(
                "plugin `beta`: new plugin, skipped" in notice
                for notice in result.notices
            ),
            result.notices,
        )

    def test_deleted_plugin_is_skipped(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._write_plugin("beta", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._git("rm", "-r", "plugins/beta")
        self._commit("remove beta")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertTrue(
            any(
                "plugin `beta`: deleted since merge base, skipped" in notice
                for notice in result.notices
            ),
            result.notices,
        )

    def test_valid_skip_trailer_passes_and_is_reported(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# typo fix\n")
        self._commit("fix typo\n\nSkip-Version-Bump: alpha - comment typo only")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertTrue(
            any(
                "plugin `alpha`: version-bump skipped by trailer" in notice
                and "comment typo only" in notice
                for notice in result.notices
            ),
            result.notices,
        )

    def test_skip_trailer_colon_separator_passes(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# edit\n")
        self._commit("edit\n\nSkip-Version-Bump: alpha : whitespace only")

        result = self._check()

        self.assertEqual([], result.errors)

    def test_skip_trailer_accepts_the_natural_colon_form(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# edit\n")
        self._commit("edit\n\nSkip-Version-Bump: alpha: comment typo only")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertTrue(
            any("comment typo only" in notice for notice in result.notices),
            result.notices,
        )

    def test_skip_trailer_unknown_plugin_fails(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# edit\n")
        self._commit("edit\n\nSkip-Version-Bump: ghost - not a plugin")

        result = self._check()

        self.assertTrue(
            any(
                "Skip-Version-Bump trailer names unknown plugin `ghost`" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_skip_trailer_empty_reason_fails(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# edit\n")
        self._commit("edit\n\nSkip-Version-Bump: alpha -   ")

        result = self._check()

        self.assertTrue(
            any("Skip-Version-Bump" in error for error in result.errors),
            result.errors,
        )
        # The skip must not silently suppress the missing bump.
        self.assertTrue(
            any("shipped content changed" in error for error in result.errors)
            or any("empty reason" in error for error in result.errors),
            result.errors,
        )

    def test_multiple_plugins_reported_independently(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._write_plugin("beta", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# alpha edit\n")
        self._set_version("alpha", "1.0.1")
        self._touch("beta", "skills/beta/SKILL.md", "# beta edit\n")
        self._commit("edit both, bump only alpha")

        result = self._check()

        self.assertTrue(
            any("plugin `beta`:" in error for error in result.errors),
            result.errors,
        )
        self.assertFalse(
            any("plugin `alpha`:" in error for error in result.errors),
            result.errors,
        )

    def test_stacked_commits_require_only_one_bump(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# step 1\n")
        self._commit("step 1")
        self._touch("alpha", "commands/alpha.md", "# step 2\n")
        self._set_version("alpha", "1.1.0")
        self._commit("step 2 with bump")

        result = self._check()

        self.assertEqual([], result.errors)
        self.assertEqual(1, result.changed_plugins)

    def test_unresolvable_base_ref_refuses(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")

        result = self._check(base="nonexistent-ref")

        self.assertIsNotNone(result.refusal)
        self.assertEqual([], result.errors)

    def test_main_returns_two_on_refusal(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")

        exit_code = version_bump.main([str(self.repo), "--base", "nonexistent-ref"])

        self.assertEqual(2, exit_code)

    def test_main_returns_one_on_missing_bump(self) -> None:
        self._write_plugin("alpha", "1.0.0")
        self._commit("base")
        self._start_feature()
        self._touch("alpha", "skills/alpha/SKILL.md", "# edit\n")
        self._commit("edit")

        exit_code = version_bump.main([str(self.repo), "--base", "main"])

        self.assertEqual(1, exit_code)

    def test_not_a_git_repository_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            result = version_bump.check_version_bumps(Path(plain), "main")

        self.assertIsNotNone(result.refusal)


if __name__ == "__main__":
    unittest.main()
