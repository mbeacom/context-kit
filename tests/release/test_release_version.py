"""Regression tests for the release version guard (`scripts/release_version.py`).

The guard's whole value is that it refuses a bad release *before* an
irreversible upload, so the cases that matter most are the negative ones: every
individual surface that can drift must, on its own, block the publish.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPOSITORY_ROOT / "scripts" / "release_version.py"

PYPROJECT = """\
[project]
name = "widget"
version = "{version}"
"""

APM = """\
# comment line
name: widget
version: {version}
keywords: [a, b]
"""

CHANGELOG = """\
# Changelog

## {version} — 2026-08-08

- Something changed.
"""


def build_plugin(root: Path, version: str = "1.2.3", **overrides: str) -> Path:
    """Write a minimal plugin tree whose surfaces all agree, then apply overrides."""
    versions = {
        "pyproject": version,
        "dunder": version,
        "plugin_json": version,
        "apm": version,
        "changelog": version,
    }
    versions.update(overrides)

    plugin = root / "widget"
    (plugin / "src" / "widget").mkdir(parents=True)
    (plugin / ".claude-plugin").mkdir()

    (plugin / "pyproject.toml").write_text(
        PYPROJECT.format(version=versions["pyproject"]), encoding="utf-8"
    )
    (plugin / "src" / "widget" / "__init__.py").write_text(
        f'"""Doc."""\n\n__version__ = "{versions["dunder"]}"\n', encoding="utf-8"
    )
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "widget", "version": versions["plugin_json"]}),
        encoding="utf-8",
    )
    (plugin / "apm.yml").write_text(
        APM.format(version=versions["apm"]), encoding="utf-8"
    )
    (plugin / "CHANGELOG.md").write_text(
        CHANGELOG.format(version=versions["changelog"]), encoding="utf-8"
    )
    return plugin


def run_guard(plugin: Path, tag: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--package",
            "widget",
            "--tag",
            tag,
            "--plugin-dir",
            str(plugin),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class ReleaseVersionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_all_surfaces_agree_passes(self) -> None:
        plugin = build_plugin(self.root)
        result = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("every version surface agrees", result.stdout)

    def test_each_surface_blocks_independently(self) -> None:
        for surface in ("pyproject", "dunder", "plugin_json", "apm", "changelog"):
            with self.subTest(surface=surface):
                root = self.root / surface
                root.mkdir()
                plugin = build_plugin(root, **{surface: "9.9.9"})
                result = run_guard(plugin, "widget/v1.2.3")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("FAIL", result.stdout)

    def test_unprefixed_tag_is_rejected(self) -> None:
        plugin = build_plugin(self.root)
        result = run_guard(plugin, "v1.2.3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match the required form", result.stderr)

    def test_tag_for_a_sibling_package_is_rejected(self) -> None:
        # A monorepo failure mode the prefix exists to prevent: releasing
        # `widget` because someone tagged a different plugin.
        plugin = build_plugin(self.root)
        result = run_guard(plugin, "gadget/v1.2.3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match the required form", result.stderr)

    def test_shell_metacharacters_in_tag_are_rejected_not_executed(self) -> None:
        # The workflow passes this value through `env:` rather than inlining it
        # into the script, so a hostile tag reaches the guard as literal text.
        # The guard must reject it as a malformed tag, never interpret it.
        canary = self.root / "canary.txt"
        hostile = [
            f'widget/v1.2.3"; touch {canary}; #',
            "widget/v1.2.3$(id)",
            "widget/v1.2.3`id`",
            "widget/v1.2.3; rm -rf /",
            "widget/v1.2.3\nwidget/v9.9.9",
        ]
        for tag in hostile:
            with self.subTest(tag=tag):
                plugin = build_plugin(self.root / f"h{abs(hash(tag))}")
                result = run_guard(plugin, tag)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse(canary.exists(), "tag was evaluated, not compared")

    def test_local_version_is_rejected(self) -> None:
        # PyPI refuses local versions outright; catching it here beats
        # discovering it at the upload step.
        plugin = build_plugin(self.root, version="1.2.3+local")
        result = run_guard(plugin, "widget/v1.2.3+local")
        self.assertEqual(result.returncode, 1)
        self.assertIn("PEP 440", result.stderr)

    def test_prerelease_version_is_accepted(self) -> None:
        plugin = build_plugin(self.root, version="1.2.3rc1")
        result = run_guard(plugin, "widget/v1.2.3rc1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distribution_name_must_match_tag_prefix(self) -> None:
        plugin = build_plugin(self.root)
        (plugin / "pyproject.toml").write_text(
            PYPROJECT.format(version="1.2.3").replace('"widget"', '"gadget"'),
            encoding="utf-8",
        )
        result = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("declares project name", result.stdout)

    def test_plugin_drift_blocks_by_default_and_is_opt_in(self) -> None:
        plugin = build_plugin(self.root, plugin_json="2.0.0", apm="2.0.0")

        blocked = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(blocked.returncode, 1, blocked.stdout)

        allowed = run_guard(plugin, "widget/v1.2.3", "--allow-plugin-drift")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        self.assertIn("drift allowed", allowed.stdout)

    def test_drift_flag_never_excuses_the_package_surfaces(self) -> None:
        # The escape hatch is scoped to the plugin manifests. It must not become
        # a way to publish a wheel whose metadata disagrees with the tag.
        plugin = build_plugin(self.root, pyproject="2.0.0")
        result = run_guard(plugin, "widget/v1.2.3", "--allow-plugin-drift")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_dynamic_version_is_rejected(self) -> None:
        plugin = build_plugin(self.root)
        (plugin / "pyproject.toml").write_text(
            '[project]\nname = "widget"\ndynamic = ["version"]\n', encoding="utf-8"
        )
        result = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("static", result.stdout)

    def test_changelog_heading_must_be_an_exact_version_match(self) -> None:
        # `## 1.2.30` must not satisfy a 1.2.3 release.
        plugin = build_plugin(self.root)
        (plugin / "CHANGELOG.md").write_text(
            CHANGELOG.format(version="1.2.30"), encoding="utf-8"
        )
        result = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("CHANGELOG.md", result.stdout)

    def test_missing_file_fails_rather_than_passing_silently(self) -> None:
        plugin = build_plugin(self.root)
        (plugin / "apm.yml").unlink()
        result = run_guard(plugin, "widget/v1.2.3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read", result.stdout)


class ShippedIndexkitTests(unittest.TestCase):
    """The guard must agree with the real package as committed."""

    def test_indexkit_surfaces_agree_with_their_own_version(self) -> None:
        plugin_dir = REPOSITORY_ROOT / "plugins" / "indexkit"
        pyproject = (plugin_dir / "pyproject.toml").read_text(encoding="utf-8")
        version = next(
            line.split("=", 1)[1].strip().strip('"')
            for line in pyproject.splitlines()
            if line.startswith("version")
        )
        result = subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "--package",
                "indexkit",
                "--tag",
                f"indexkit/v{version}",
                "--plugin-dir",
                str(plugin_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
