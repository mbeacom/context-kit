"""Regression tests for release-note rendering and the missing-tag planner.

`scripts/release_notes.py` feeds two workflows that write to the repository:
`tag-releases.yml` (tags and releases for plugins) and the package release
workflows (GitHub releases after a PyPI upload). The cases that matter most are
the ones that would publish the wrong thing: a changelog section bleeding into
its neighbour, an unlisted stub being tagged, or a package tag being automated.

Every test builds a throwaway repository on disk; none touches the network.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "scripts" / "release_notes.py"
WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"

ALPHA_CHANGELOG = """\
# Changelog

## 1.2.10 — 2026-10-26

- A later release that must not leak into 1.2.1.

## 1.2.1 — 2026-10-25

- Fix the thing.
  Wrapped continuation line.

### Notes

- A subsection belongs to its release.

## 1.2.0 — 2026-10-01

- Earlier release.
"""

PACKAGE_CHANGELOG = """\
# Changelog

## {version} — 2026-10-25

- Package change.
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def add_plugin(root: Path, directory: str, version: str, changelog: str) -> None:
    manifest = {"name": directory, "version": version}
    write(
        root / "plugins" / directory / ".claude-plugin" / "plugin.json",
        json.dumps(manifest),
    )
    write(root / "plugins" / directory / "CHANGELOG.md", changelog)


def build_repo(root: Path) -> Path:
    """A marketplace shipping `alpha`, `indexkit`, and `memory`; `stub` is unlisted."""
    add_plugin(root, "alpha", "1.2.1", ALPHA_CHANGELOG)
    add_plugin(root, "indexkit", "0.6.6", PACKAGE_CHANGELOG.format(version="0.6.6"))
    add_plugin(root, "memory", "0.8.2", PACKAGE_CHANGELOG.format(version="0.8.2"))
    add_plugin(root, "stub", "0.0.1", PACKAGE_CHANGELOG.format(version="0.0.1"))
    marketplace = {
        "name": "context-kit",
        "plugins": [
            {"name": "alpha", "source": "./plugins/alpha"},
            {"name": "indexkit", "source": "./plugins/indexkit"},
            {"name": "memory", "source": "./plugins/memory"},
        ],
    }
    write(root / ".claude-plugin" / "marketplace.json", json.dumps(marketplace))
    return root


def run(
    root: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )


class RenderPlugin(unittest.TestCase):
    def test_plugin_body_matches_the_release_format(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(root, "render", "--tag", "alpha/v1.2.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "## Changes in 1.2.1\n"
            "\n"
            "- Fix the thing.\n"
            "  Wrapped continuation line.\n"
            "\n"
            "### Notes\n"
            "\n"
            "- A subsection belongs to its release.\n"
            "\n"
            "## Install\n"
            "\n"
            "```bash\n"
            "copilot plugin marketplace add mbeacom/context-kit\n"
            "copilot plugin install alpha@context-kit\n"
            "```\n"
            "\n"
            "In Claude Code: `/plugin marketplace add mbeacom/context-kit`, "
            "then `/plugin install alpha@context-kit`.\n",
        )

    def test_version_prefix_never_selects_a_longer_version(self) -> None:
        """1.2.1 must not match the 1.2.10 heading that precedes it."""
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(root, "render", "--tag", "alpha/v1.2.1")
        self.assertNotIn("later release", result.stdout)
        self.assertNotIn("Earlier release", result.stdout)

    def test_plugin_dir_renders_the_manifest_version(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            by_dir = run(root, "render", "--plugin-dir", "plugins/alpha")
            by_tag = run(root, "render", "--tag", "alpha/v1.2.1")
        self.assertEqual(by_dir.returncode, 0, by_dir.stderr)
        self.assertEqual(by_dir.stdout, by_tag.stdout)

    def test_missing_changelog_section_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(root, "render", "--tag", "alpha/v9.9.9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no '## 9.9.9' section", result.stderr)

    def test_unshipped_or_misprefixed_tags_fail(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            for tag in (
                "stub/v0.0.1",
                "memory/v0.8.2",
                "alpha-1.2.1",
                "alpha/v1.2.1;rm",
            ):
                with self.subTest(tag=tag):
                    self.assertEqual(run(root, "render", "--tag", tag).returncode, 1)

    def test_output_file(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            out = Path(tmp) / "notes.md"
            result = run(root, "render", "--tag", "alpha/v1.2.1", "--output", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertTrue(
                out.read_text(encoding="utf-8").startswith("## Changes in 1.2.1\n")
            )


class RenderPackage(unittest.TestCase):
    def test_package_body_uses_the_distribution_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(root, "render", "--tag", "memorykit/v0.8.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = result.stdout
        self.assertTrue(
            body.startswith(
                "```bash\n"
                "pip install memorykit==0.8.2          # or: uv tool install memorykit==0.8.2\n"
                "```\n\n## Changes in 0.8.2\n\n- Package change.\n\n## Provenance\n"
            ),
            body,
        )
        self.assertIn("integrity endpoint — PyPI's JSON API", body)
        self.assertIn(
            "for file in memorykit-0.8.2-py3-none-any.whl memorykit-0.8.2.tar.gz; do",
            body,
        )
        self.assertIn(
            '"https://pypi.org/integrity/memorykit/0.8.2/${file}/provenance"', body
        )
        self.assertIn(
            "| jq -e '.attestation_bundles[0].publisher | {repository, workflow}'", body
        )
        self.assertTrue(
            body.endswith(
                "Both report `mbeacom/context-kit` / `release-memorykit.yml`.\n"
            )
        )
        self.assertNotIn("## Install", body)

    def test_package_plugin_dir_maps_to_its_distribution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(root, "render", "--plugin-dir", "plugins/indexkit")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pip install indexkit==0.6.6", result.stdout)
        self.assertIn("`release-indexkit.yml`", result.stdout)


class Plan(unittest.TestCase):
    def plan(self, root: Path, tags: str, releases: str | None = None) -> list[dict]:
        args = ["plan", "--existing-tags-file", "-", "--format", "json"]
        if releases is not None:
            path = root / "releases.txt"
            path.write_text(releases, encoding="utf-8")
            args += ["--existing-releases-file", str(path)]
        result = run(root, *args, stdin=tags)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_only_shipped_plugins_are_planned(self) -> None:
        with TemporaryDirectory() as tmp:
            entries = self.plan(build_repo(Path(tmp)), "")
        self.assertEqual(
            [e["tag"] for e in entries],
            ["alpha/v1.2.1", "indexkit/v0.6.6", "memorykit/v0.8.2"],
        )

    def test_missing_tags_get_the_right_action(self) -> None:
        with TemporaryDirectory() as tmp:
            entries = self.plan(build_repo(Path(tmp)), "alpha/v1.2.0\nmemory/v0.8.2\n")
        actions = {e["tag"]: e["action"] for e in entries}
        self.assertEqual(
            actions,
            {
                "alpha/v1.2.1": "tag-and-release",
                # A package tag is never automated, and `memory/v...` is not
                # the package's tag: the distribution name is the prefix.
                "indexkit/v0.6.6": "maintainer-tag",
                "memorykit/v0.8.2": "maintainer-tag",
            },
        )

    def test_everything_tagged_means_nothing_to_do(self) -> None:
        tags = "alpha/v1.2.1\nindexkit/v0.6.6\nmemorykit/v0.8.2\n"
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            entries = self.plan(root, tags, releases=tags)
            text = run(root, "plan", "--existing-tags-file", "-", stdin=tags)
            tsv = run(
                root, "plan", "--existing-tags-file", "-", "--format", "tsv", stdin=tags
            )
        self.assertEqual({e["action"] for e in entries}, {"none"})
        self.assertEqual(text.stdout, "Every shipped plugin version is tagged.\n")
        self.assertEqual(tsv.stdout, "")

    def test_tag_without_release_is_repaired(self) -> None:
        """A run that pushed the tag and then failed must be finished, not skipped."""
        tags = "alpha/v1.2.1\nindexkit/v0.6.6\nmemorykit/v0.8.2\n"
        with TemporaryDirectory() as tmp:
            entries = self.plan(
                build_repo(Path(tmp)), tags, releases="memorykit/v0.8.2\n"
            )
        actions = {e["tag"]: e["action"] for e in entries}
        self.assertEqual(actions["alpha/v1.2.1"], "release")
        # The package workflow owns package releases; the planner leaves them.
        self.assertEqual(actions["indexkit/v0.6.6"], "none")

    def test_tsv_rows_are_tab_separated_and_actionable_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            result = run(
                root,
                "plan",
                "--existing-tags-file",
                "-",
                "--format",
                "tsv",
                stdin="indexkit/v0.6.6\n",
            )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "tag-and-release\talpha/v1.2.1\talpha\talpha 1.2.1",
                "maintainer-tag\tmemorykit/v0.8.2\tmemory\tmemorykit 0.8.2",
            ],
        )

    def test_malformed_version_is_refused(self) -> None:
        """Versions reach tag names and shell variables; free text must not."""
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            add_plugin(root, "alpha", "1.2.1 $(id)", ALPHA_CHANGELOG)
            result = run(root, "plan", "--existing-tags-file", "-", stdin="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid version", result.stderr)

    def test_defaults_to_git_tags(self) -> None:
        with TemporaryDirectory() as tmp:
            root = build_repo(Path(tmp))
            git = [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
            ]
            # Ignore the contributor's global config (signing, hooks, templates).
            env = {
                **os.environ,
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "init"]):
                subprocess.run([*git, *args], check=True, env=env)
            subprocess.run([*git, "tag", "alpha/v1.2.1"], check=True, env=env)
            result = run(root, "plan", "--format", "tsv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("alpha/v1.2.1", result.stdout)
        self.assertIn("indexkit/v0.6.6", result.stdout)


class RealRepository(unittest.TestCase):
    """The real catalog must stay renderable, or the release jobs fail late."""

    def test_every_shipped_plugin_renders_at_its_current_version(self) -> None:
        result = run(
            REPOSITORY_ROOT, "plan", "--existing-tags-file", "-", "--format", "json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in json.loads(result.stdout):
            with self.subTest(tag=entry["tag"]):
                rendered = run(REPOSITORY_ROOT, "render", "--tag", entry["tag"])
                self.assertEqual(rendered.returncode, 0, rendered.stderr)


class PackageWorkflowWiring(unittest.TestCase):
    """The GitHub release must follow the publish, never a rehearsal."""

    def test_release_job_is_gated_like_publish(self) -> None:
        for package in ("indexkit", "memorykit"):
            with self.subTest(package=package):
                text = (WORKFLOWS / f"release-{package}.yml").read_text(
                    encoding="utf-8"
                )
                job = text.split("\n  github-release:\n", 1)[1]
                self.assertIn("needs: [verify, publish]", job)
                self.assertIn(
                    "github.event_name == 'push' &&\n"
                    f"      startsWith(github.ref, 'refs/tags/{package}/v')",
                    job,
                )
                self.assertIn("contents: write", job)
                for flag in ("--verify-tag", "--latest=false", "--clobber"):
                    self.assertIn(flag, job)
                self.assertIn("scripts/release_notes.py render", job)
                self.assertIn("SHA256SUMS", job)
                self.assertIn(f"name: {package}-published", job)
                # Write access exists only on the release job.
                before = text.split("\n  github-release:\n", 1)[0]
                self.assertNotIn("contents: write", before)
                # The attestations are handed on from the publish job.
                self.assertIn("dist/*.publish.attestation", before)


class TagWorkflowWiring(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (WORKFLOWS / "tag-releases.yml").read_text(encoding="utf-8")

    def test_runs_on_main_with_a_dry_run_dispatch(self) -> None:
        self.assertIn("branches: [main]", self.text)
        self.assertIn("dry_run:", self.text)
        self.assertIn("inputs.dry_run == false", self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)

    def test_write_access_only_on_the_release_job(self) -> None:
        plan, release = self.text.split("\n  release:\n", 1)
        self.assertNotIn("contents: write", plan)
        self.assertIn("contents: write", release)

    def test_package_tags_are_never_automated(self) -> None:
        self.assertIn("grep -E $'^(tag-and-release|release)\\t'", self.text)
        self.assertIn("indexkit/*|memorykit/*)", self.text)
        self.assertIn("maintainer-tag", self.text)

    def test_writes_are_idempotent_and_not_latest(self) -> None:
        self.assertIn("git ls-remote --exit-code --tags origin", self.text)
        self.assertIn('gh release view "$tag"', self.text)
        self.assertIn("--verify-tag", self.text)
        self.assertIn("--latest=false", self.text)
        self.assertIn("cancel-in-progress: false", self.text)


if __name__ == "__main__":
    unittest.main()
