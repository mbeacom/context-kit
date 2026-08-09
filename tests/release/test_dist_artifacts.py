"""Regression tests for the built-distribution assertion.

The bug these exist for: the first version of this check counted every regular
file in ``dist/`` and so failed on ``uv build``'s own ``dist/.gitignore``. It
reached CI because nothing exercised the assertion against a directory shaped
the way ``uv build`` actually leaves one.

None of these need a network build. ``uv build``'s output layout is reproduced
from disk — two distributions plus a one-byte ``.gitignore`` containing ``*``.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPOSITORY_ROOT / "scripts" / "check_dist_artifacts.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "release-indexkit.yml"

PACKAGE = "indexkit"
VERSION = "0.6.1"
SDIST = f"{PACKAGE}-{VERSION}.tar.gz"
WHEEL = f"{PACKAGE}-{VERSION}-py3-none-any.whl"


def build_dist(root: Path, names: tuple[str, ...]) -> Path:
    """Create a dist directory holding files with the given names."""
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for name in names:
        (dist / name).write_bytes(b"not a real archive")
    return dist


def run_check(dist: Path, version: str = VERSION) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--dist-dir",
            str(dist),
            "--package",
            PACKAGE,
            "--version",
            version,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class DistArtifactCheck(unittest.TestCase):
    def test_accepts_exactly_the_two_expected_distributions(self) -> None:
        with TemporaryDirectory() as tmp:
            dist = build_dist(Path(tmp), (SDIST, WHEEL))
            result = run_check(dist)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_uv_build_gitignore_does_not_fail_the_check(self) -> None:
        """The exact CI failure: uv build writes a one-byte dist/.gitignore.

        The distributions are correct and complete; a build-tool bookkeeping
        file is not a publishable artifact and must not block the release.
        """
        with TemporaryDirectory() as tmp:
            dist = build_dist(Path(tmp), (SDIST, WHEEL))
            (dist / ".gitignore").write_text("*", encoding="utf-8")

            # Guard the premise: the old logic counted this file, and a
            # dotfile-hiding listing is what made that invisible in the log.
            self.assertEqual(len([p for p in dist.iterdir() if p.is_file()]), 3)

            result = run_check(dist)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(".gitignore", result.stdout)
        self.assertIn("not a distribution", result.stdout)

    def test_reports_but_tolerates_other_non_distribution_files(self) -> None:
        with TemporaryDirectory() as tmp:
            dist = build_dist(Path(tmp), (SDIST, WHEEL))
            (dist / "build.log").write_text("noise", encoding="utf-8")
            result = run_check(dist)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("build.log", result.stdout)

    def test_rejects_a_stale_distribution_from_another_version(self) -> None:
        """The risk the check actually exists for."""
        for stale in (
            f"{PACKAGE}-0.6.0-py3-none-any.whl",
            f"{PACKAGE}-0.6.0.tar.gz",
            f"{PACKAGE}-0.7.0rc1-py3-none-any.whl",
        ):
            with self.subTest(stale=stale), TemporaryDirectory() as tmp:
                dist = build_dist(Path(tmp), (SDIST, WHEEL, stale))
                result = run_check(dist)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("unexpected distribution", result.stdout)
                self.assertIn(stale, result.stderr)

    def test_rejects_a_missing_distribution(self) -> None:
        for present, missing in ((SDIST, WHEEL), (WHEEL, SDIST)):
            with self.subTest(missing=missing), TemporaryDirectory() as tmp:
                dist = build_dist(Path(tmp), (present,))
                result = run_check(dist)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("missing", result.stdout)
                self.assertIn(missing, result.stderr)

    def test_rejects_a_version_the_tag_did_not_ask_for(self) -> None:
        with TemporaryDirectory() as tmp:
            dist = build_dist(Path(tmp), (SDIST, WHEEL))
            result = run_check(dist, version="0.7.0")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_rejects_an_empty_or_absent_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            empty = build_dist(Path(tmp), ())
            self.assertEqual(run_check(empty).returncode, 1)
            self.assertEqual(run_check(Path(tmp) / "nope").returncode, 1)

    def test_a_directory_holding_only_bookkeeping_is_not_a_pass(self) -> None:
        """`.gitignore` is ignored, but ignoring it must not empty the check."""
        with TemporaryDirectory() as tmp:
            dist = build_dist(Path(tmp), ())
            (dist / ".gitignore").write_text("*", encoding="utf-8")
            result = run_check(dist)
        self.assertEqual(result.returncode, 1, result.stdout)


class WorkflowWiring(unittest.TestCase):
    """The check only protects a release if the workflow still calls it."""

    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_invokes_the_check(self) -> None:
        self.assertIn("check_dist_artifacts.py", self.workflow)

    def test_workflow_does_not_count_every_regular_file(self) -> None:
        """The shape of the original bug, kept out by name."""
        self.assertNotIn("find dist -maxdepth 1 -type f\n", self.workflow)
        self.assertNotIn("unexpected artifacts in dist/", self.workflow)

    def test_workflow_listing_shows_dotfiles(self) -> None:
        """A listing that hides dotfiles is what made the bug unreadable."""
        self.assertIn("ls -la dist", self.workflow)
        self.assertNotIn("ls -l dist\n", self.workflow)

    def test_workflow_uploads_only_distributions(self) -> None:
        """Nothing but a distribution should reach the publish job."""
        self.assertIn("plugins/indexkit/dist/*.whl", self.workflow)
        self.assertIn("plugins/indexkit/dist/*.tar.gz", self.workflow)
        self.assertNotIn("path: plugins/indexkit/dist/\n", self.workflow)

    def test_dispatch_cannot_reach_the_publish_job(self) -> None:
        """A ref check alone does not stop a rehearsal from publishing.

        `workflow_dispatch` can be run against a tag, in which case
        `github.ref` is `refs/tags/...` exactly as it is for a tag push. The
        guard therefore has to test the *event*, or the dispatch path silently
        gains the one capability it exists to withhold — and the failure would
        only ever be observed as an irreversible upload.
        """
        # Assert the *conjoined* expression, not two independent substrings.
        # Separate checks would still pass if `&&` were swapped for `||`, which
        # restores exactly the bug this test names: either predicate alone would
        # admit a tag-targeted dispatch to the publish job.
        #
        # The literal spans lines because the condition is a YAML folded block;
        # matching it verbatim is what makes the conjunction part of the
        # assertion rather than an assumption about it.
        self.assertIn(
            "github.event_name == 'push' &&\n"
            "      startsWith(github.ref, 'refs/tags/indexkit/v')",
            self.workflow,
            "publish must require a push event AND the indexkit tag prefix, "
            "conjoined in one expression",
        )

    def test_workflow_pins_attestations(self) -> None:
        """PEP 740 provenance is the upstream default, so losing it is silent.

        The action is pinned to a moving `release/v1`, and PyPI's JSON API
        reports `provenance: null` for every file whether attested or not — so
        a flipped upstream default would not surface anywhere an operator
        looks. Stating the input is what makes that regression detectable.
        """
        self.assertIn("attestations: true", self.workflow)
        self.assertNotIn("attestations: false", self.workflow)

    def test_publish_job_can_mint_an_oidc_token(self) -> None:
        """Attestations and Trusted Publishing both need `id-token: write`."""
        self.assertIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
