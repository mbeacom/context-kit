#!/usr/bin/env python3
"""Reconcile a release tag against every version surface of a published package.

A PyPI upload is irreversible: a file uploaded under the wrong version cannot be
replaced, only yanked. The cheapest place to catch a mismatch is *before* the
build, so this runs as the first step of the release workflow and blocks it.

The surfaces checked, and why each one can drift independently:

``<package>/vX.Y.Z``  the git tag; typed by a human, so it is the surface most
                      likely to be wrong.
``pyproject.toml``    what actually lands in the wheel metadata and becomes the
                      PyPI release. This is the version that matters to users.
``src/<mod>/__init__``what ``indexkit --version`` prints at runtime. Divergence
                      here is invisible to packaging but misleads bug reports.
``plugin.json``       the Claude Code / Copilot cache key (ADR-0005).
``apm.yml``           the APM mirror, kept strictly in lockstep with the above.
``CHANGELOG.md``      release notes; a publish with no entry ships unexplained.

ADR-0006 notes that the plugin version and the package version are two artifacts
that *can* drift. We choose parity by default anyway: one number for one thing,
whichever channel delivered it. Drift stays possible but must be requested out
loud with ``--allow-plugin-drift``, mirroring the auditable escape hatch
ADR-0005 uses for version bumps.

Exit codes: 0 = every surface agrees; 1 = mismatch; 2 = usage or read error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    print(
        "ERROR: this script needs Python 3.11+ for tomllib "
        f"(running {sys.version_info.major}.{sys.version_info.minor})",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

# PEP 440 public release, optionally pre/post/dev. Deliberately narrower than the
# full grammar: local versions (`+local`) cannot be uploaded to PyPI at all, and
# accepting one here would push that failure to the last possible step.
VERSION_RE = re.compile(
    r"^\d+(\.\d+)*"  # release segment
    r"((a|b|rc)\d+)?"  # pre-release
    r"(\.post\d+)?"  # post-release
    r"(\.dev\d+)?$"  # dev release
)

DUNDER_VERSION_RE = re.compile(
    r"^__version__\s*=\s*(['\"])(?P<version>[^'\"]+)\1", re.MULTILINE
)


class CheckError(Exception):
    """A surface could not be read. Distinct from a surface that disagrees."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckError(f"cannot read {path}: {exc}") from exc


def parse_tag(tag: str, package: str) -> str:
    """Extract the version from ``<package>/v<X.Y.Z>``.

    The package prefix is not decoration. This repository ships 14 plugins from
    one tree, so a bare ``v0.6.0`` would not say *what* is at 0.6.0, and two
    packages could never be released independently. The exact form is the one
    ``docs/releasing.md`` already defines for plugin releases — the package
    release reuses it rather than introducing a second scheme.
    """
    prefix = f"{package}/v"
    if not tag.startswith(prefix):
        raise CheckError(f"tag {tag!r} does not match the required form {prefix}X.Y.Z")
    version = tag[len(prefix) :]
    if not VERSION_RE.match(version):
        raise CheckError(
            f"tag {tag!r} carries version {version!r}, which is not an "
            "uploadable PEP 440 release (no local versions, no arbitrary text)"
        )
    return version


def pyproject_version(path: Path, expected_name: str) -> str:
    try:
        data = tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError as exc:
        raise CheckError(f"{path} is not valid TOML: {exc}") from exc
    project = data.get("project")
    if not isinstance(project, dict):
        raise CheckError(f"{path} has no [project] table")
    name = project.get("name")
    if name != expected_name:
        raise CheckError(
            f"{path} declares project name {name!r}, but the tag releases "
            f"{expected_name!r}; the tag prefix and the distribution name must agree"
        )
    version = project.get("version")
    if not isinstance(version, str):
        raise CheckError(
            f"{path} has no static [project].version "
            "(a dynamic version cannot be reconciled with a tag before the build)"
        )
    return version


def dunder_version(path: Path) -> str:
    match = DUNDER_VERSION_RE.search(_read(path))
    if not match:
        raise CheckError(f"{path} has no module-level __version__ assignment")
    return match.group("version")


def json_version(path: Path) -> str:
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise CheckError(f"{path} is not valid JSON: {exc}") from exc
    version = data.get("version")
    if not isinstance(version, str):
        raise CheckError(f"{path} has no string `version` field")
    return version


def apm_version(path: Path) -> str:
    """Read the top-level ``version:`` scalar without a YAML dependency.

    Mirrors the tolerance of ``check-manifests.sh``: only unindented keys count,
    a trailing comment is stripped, and matching quotes are unwrapped.
    """
    for line in _read(path).splitlines():
        if not line or line[0].isspace() or not line.startswith("version"):
            continue
        key, _, raw = line.partition(":")
        if key.strip() != "version":
            continue
        value = raw.split("#", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            return value
    raise CheckError(f"{path} has no top-level `version:` key")


def changelog_has_version(path: Path, version: str) -> bool:
    """True when a heading names this version, e.g. ``## 0.6.0 — 2026-08-08``."""
    pattern = re.compile(
        rf"^#{{1,6}}\s.*(?<![\w.]){re.escape(version)}(?![\w.])", re.MULTILINE
    )
    return bool(pattern.search(_read(path)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_version.py",
        description="Verify a release tag matches every version surface of a package.",
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Distribution name, and the tag prefix (e.g. indexkit).",
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Release tag, of the form <package>/vX.Y.Z.",
    )
    parser.add_argument(
        "--plugin-dir",
        required=True,
        type=Path,
        help="Plugin directory holding pyproject.toml, src/, and the manifests.",
    )
    parser.add_argument(
        "--module",
        help="Import name under src/ (defaults to the package name with - as _).",
    )
    parser.add_argument(
        "--allow-plugin-drift",
        action="store_true",
        help=(
            "Permit plugin.json/apm.yml to carry a different version from the "
            "package. Off by default; ADR-0008 explains why parity is the default."
        ),
    )
    args = parser.parse_args(argv)

    plugin_dir: Path = args.plugin_dir
    module = args.module or args.package.replace("-", "_")

    try:
        expected = parse_tag(args.tag, args.package)
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # (label, path, reader, blocking-on-mismatch)
    surfaces: list[tuple[str, Path, object, bool]] = [
        (
            "pyproject.toml [project].version",
            plugin_dir / "pyproject.toml",
            lambda p: pyproject_version(p, args.package),
            True,
        ),
        (
            f"src/{module}/__init__.py __version__",
            plugin_dir / "src" / module / "__init__.py",
            dunder_version,
            True,
        ),
        (
            ".claude-plugin/plugin.json version",
            plugin_dir / ".claude-plugin" / "plugin.json",
            json_version,
            not args.allow_plugin_drift,
        ),
        (
            "apm.yml version",
            plugin_dir / "apm.yml",
            apm_version,
            not args.allow_plugin_drift,
        ),
    ]

    print(f"Release tag:      {args.tag}")
    print(f"Expected version: {expected}")
    print()

    failures: list[str] = []
    for label, path, reader, blocking in surfaces:
        try:
            found = reader(path)  # type: ignore[operator]
        except CheckError as exc:
            print(f"FAIL  {label}: {exc}")
            failures.append(label)
            continue
        if found == expected:
            print(f"ok    {label}: {found}")
        elif blocking:
            print(f"FAIL  {label}: {found} (expected {expected})")
            failures.append(label)
        else:
            print(f"warn  {label}: {found} (drift allowed by --allow-plugin-drift)")

    changelog = plugin_dir / "CHANGELOG.md"
    try:
        if changelog_has_version(changelog, expected):
            print(f"ok    CHANGELOG.md: heading for {expected}")
        else:
            print(f"FAIL  CHANGELOG.md: no heading naming {expected}")
            failures.append("CHANGELOG.md")
    except CheckError as exc:
        print(f"FAIL  CHANGELOG.md: {exc}")
        failures.append("CHANGELOG.md")

    print()
    if failures:
        print(
            f"ERROR: {len(failures)} version surface(s) disagree with tag "
            f"{args.tag}: {', '.join(failures)}",
            file=sys.stderr,
        )
        print(
            "Fix the sources and move the tag; do not publish a mismatched "
            "version — PyPI uploads cannot be replaced.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: every version surface agrees on {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
