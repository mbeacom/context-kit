#!/usr/bin/env python3
"""Fail CI when shipped plugin content changes without a version bump.

Claude Code uses ``plugin.json`` ``version`` as its cache key: changing shipped
content without bumping the version ships nothing to users. The other gates are
diff-free and run under both pre-commit and CI; this one needs a merge base, so
it is CI-only (still runnable by hand via ``--base``). It compares
``merge-base..HEAD`` (never ``HEAD~1``) so a bump is required once per pull
request, not once per commit.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Reuse the release-readiness semver primitives rather than duplicating a
# subtly-different regex; both gates must agree on what "a version" is.
_RR_PATH = Path(__file__).resolve().with_name("release_readiness.py")
_RR_SPEC = importlib.util.spec_from_file_location("release_readiness", _RR_PATH)
assert _RR_SPEC and _RR_SPEC.loader
release_readiness = importlib.util.module_from_spec(_RR_SPEC)
sys.modules.setdefault(_RR_SPEC.name, release_readiness)
_RR_SPEC.loader.exec_module(release_readiness)

SEMVER_CORE_RE = release_readiness.SEMVER_CORE_RE
_is_semver = release_readiness._is_semver

MANIFEST_RELPATH = ".claude-plugin/plugin.json"

# Everything under plugins/<name>/ counts as SHIPPED content that can change
# installed behavior EXCEPT these exempt paths. The set is fail-closed: any new
# path type that is not listed here is treated as shipped and DOES require a
# bump. Rationale, per entry:
#   - CHANGELOG.md: the release note itself; the release-readiness gate already
#     ties it to the version, and it changes on every bump by definition.
#   - README.md / LICENSE: human documentation and licensing text; not code an
#     installed plugin executes.
#   - tests/**: never installed; exercise the plugin, not shipped behavior.
#   - docs/**: in-plugin documentation, not executed.
#   - scripts/test-*.sh: test-runner wrappers (siblings of check-*.sh); they run
#     tests, they are not part of what a user installs and runs.
# Amend this set deliberately and in review; keep it narrow.
EXEMPT_FILES = frozenset({"CHANGELOG.md", "README.md", "LICENSE"})
EXEMPT_DIR_PREFIXES = ("tests/", "docs/")

# Skip-Version-Bump: <plugin-name> - <reason>
# Separator mirrors RELEASE_HEADING_RE in release_readiness.py (em/en dash,
# hyphen, or colon). A line matching the prefix but not the full pattern, or a
# reason that is empty, is an ERROR — skipping must never be silent.
SKIP_PREFIX_RE = re.compile(r"^\s*Skip-Version-Bump\s*:", re.IGNORECASE)
SKIP_TRAILER_RE = re.compile(
    r"^\s*Skip-Version-Bump\s*:\s+(?P<plugin>\S+)\s*(?:—|–|-|:)\s+(?P<reason>.+)$",
    re.IGNORECASE,
)


@dataclass
class VersionBumpResult:
    errors: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    refusal: str | None = None
    base_ref: str | None = None
    merge_base: str | None = None
    checked_plugins: int = 0
    changed_plugins: int = 0


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )


def _rev_exists(repo_root: Path, ref: str) -> bool:
    result = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return result.returncode == 0 and bool(result.stdout.strip())


def resolve_base_ref(repo_root: Path, explicit: str | None) -> str | None:
    """Resolve the base ref to diff against, in documented priority order.

    Priority: explicit ``--base``; ``$GITHUB_BASE_REF`` as ``origin/<ref>``;
    ``origin/main``; then ``main``. Returns ``None`` when nothing resolves so
    the caller can refuse rather than pass silently.
    """
    if explicit:
        return explicit if _rev_exists(repo_root, explicit) else None
    github_base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if github_base:
        candidate = f"origin/{github_base}"
        if _rev_exists(repo_root, candidate):
            return candidate
        if _rev_exists(repo_root, github_base):
            return github_base
    for candidate in ("origin/main", "main"):
        if _rev_exists(repo_root, candidate):
            return candidate
    return None


def _precedence_key(version: str) -> tuple[Any, ...]:
    """Return a comparable key implementing semver precedence.

    Numeric identifiers compare numerically; alphanumeric compare lexically and
    outrank numeric; a prerelease has lower precedence than its release; build
    metadata is ignored.
    """
    match = SEMVER_CORE_RE.fullmatch(version)
    assert match is not None
    core = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    prerelease = match.group(4)
    if prerelease is None:
        # A release outranks any prerelease of the same core version.
        return (*core, (1,))
    identifiers: list[tuple[int, int, str]] = []
    for identifier in prerelease.split("."):
        if identifier.isdigit():
            identifiers.append((0, int(identifier), ""))
        else:
            identifiers.append((1, 0, identifier))
    return (*core, (0, tuple(identifiers)))


def _changed_paths(repo_root: Path, merge_base: str) -> list[str]:
    result = _git(repo_root, "diff", "--name-only", f"{merge_base}..HEAD")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _plugin_of(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "plugins":
        return parts[1]
    return None


def _is_shipped(rel_path: str) -> bool:
    """Classify a plugin-relative path. Fail-closed: unknown paths are shipped."""
    if rel_path in EXEMPT_FILES:
        return False
    if any(rel_path.startswith(prefix) for prefix in EXEMPT_DIR_PREFIXES):
        return False
    parts = rel_path.split("/")
    if len(parts) == 2 and parts[0] == "scripts":
        name = parts[1]
        if name.startswith("test-") and name.endswith(".sh"):
            return False
    return True


def _working_tree_plugins(repo_root: Path) -> set[str]:
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.is_dir():
        return set()
    names: set[str] = set()
    for child in sorted(plugins_dir.iterdir()):
        if child.is_dir() and (child / MANIFEST_RELPATH).is_file():
            names.add(child.name)
    return names


def _merge_base_plugins(repo_root: Path, merge_base: str) -> set[str]:
    result = _git(
        repo_root, "ls-tree", "-r", "--name-only", merge_base, "--", "plugins"
    )
    if result.returncode != 0:
        return set()
    suffix = "/" + MANIFEST_RELPATH
    names: set[str] = set()
    for line in result.stdout.splitlines():
        name = _plugin_of(line)
        if name is not None and line == f"plugins/{name}{suffix}":
            names.add(name)
    return names


def _version_at(repo_root: Path, ref: str, name: str, errors: list[str]) -> str | None:
    result = _git(repo_root, "show", f"{ref}:plugins/{name}/{MANIFEST_RELPATH}")
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(
            f"plugin `{name}`: cannot parse plugin.json at merge base {ref[:12]}: {exc}"
        )
        return None
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not _is_semver(version):
        errors.append(
            f"plugin `{name}`: merge-base plugin.json version is missing or not "
            "semantic versioning"
        )
        return None
    return version


def _version_now(repo_root: Path, name: str, errors: list[str]) -> str | None:
    manifest_path = repo_root / "plugins" / name / MANIFEST_RELPATH
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"plugin `{name}`: cannot parse working-tree plugin.json: {exc}")
        return None
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not _is_semver(version):
        errors.append(
            f"plugin `{name}`: working-tree plugin.json version is missing or not "
            "semantic versioning"
        )
        return None
    return version


def _collect_skips(
    repo_root: Path,
    merge_base: str,
    known_plugins: set[str],
    errors: list[str],
) -> dict[str, str]:
    result = _git(repo_root, "log", "--format=%B%x00", f"{merge_base}..HEAD")
    skips: dict[str, str] = {}
    for line in result.stdout.replace("\x00", "\n").splitlines():
        if not SKIP_PREFIX_RE.match(line):
            continue
        match = SKIP_TRAILER_RE.match(line)
        if match is None:
            errors.append(
                f"malformed Skip-Version-Bump trailer (need "
                f"`Skip-Version-Bump: <plugin> - <reason>`): {line.strip()!r}"
            )
            continue
        plugin = match.group("plugin")
        reason = match.group("reason").strip()
        if not reason:
            errors.append(
                f"Skip-Version-Bump trailer for `{plugin}` has an empty reason"
            )
            continue
        if plugin not in known_plugins:
            errors.append(f"Skip-Version-Bump trailer names unknown plugin `{plugin}`")
            continue
        skips[plugin] = reason
    return skips


def check_version_bumps(repo_root: Path, base: str | None) -> VersionBumpResult:
    repo_root = repo_root.resolve()
    toplevel = _git(repo_root, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        return VersionBumpResult(refusal=f"not a git repository: {repo_root}")

    base_ref = resolve_base_ref(repo_root, base)
    if base_ref is None:
        detail = f"`{base}`" if base else "GITHUB_BASE_REF, origin/main, or main"
        return VersionBumpResult(
            refusal=(
                f"cannot resolve a base ref ({detail}); pass --base <ref> or fetch "
                "history (fetch-depth: 0)"
            )
        )

    merge_base_result = _git(repo_root, "merge-base", base_ref, "HEAD")
    merge_base = merge_base_result.stdout.strip()
    if merge_base_result.returncode != 0 or not merge_base:
        return VersionBumpResult(
            refusal=(
                f"no merge base between {base_ref} and HEAD (shallow clone?); "
                "fetch history with fetch-depth: 0"
            )
        )

    result = VersionBumpResult(base_ref=base_ref, merge_base=merge_base)
    working_plugins = _working_tree_plugins(repo_root)
    result.checked_plugins = len(working_plugins)
    skips = _collect_skips(repo_root, merge_base, working_plugins, result.errors)

    changed_by_plugin: dict[str, list[str]] = {}
    for path in _changed_paths(repo_root, merge_base):
        name = _plugin_of(path)
        if name is None:
            continue
        rel_path = path[len(f"plugins/{name}/") :]
        changed_by_plugin.setdefault(name, []).append(rel_path)

    base_plugins = _merge_base_plugins(repo_root, merge_base)

    for name in sorted(changed_by_plugin):
        rel_paths = changed_by_plugin[name]
        if name not in working_plugins:
            if name in base_plugins:
                result.notices.append(
                    f"plugin `{name}`: deleted since merge base, skipped"
                )
            continue
        if name not in base_plugins:
            result.notices.append(f"plugin `{name}`: new plugin, skipped")
            continue

        shipped = sorted(rel for rel in rel_paths if _is_shipped(rel))
        if not shipped:
            continue
        result.changed_plugins += 1

        if name in skips:
            result.notices.append(
                f"plugin `{name}`: version-bump skipped by trailer ({skips[name]})"
            )
            continue

        base_version = _version_at(repo_root, merge_base, name, result.errors)
        head_version = _version_now(repo_root, name, result.errors)
        if base_version is None or head_version is None:
            continue
        if _precedence_key(head_version) <= _precedence_key(base_version):
            joined = ", ".join(f"plugins/{name}/{rel}" for rel in shipped)
            result.errors.append(
                f"plugin `{name}`: shipped content changed ({joined}) but version "
                f"did not increase ({base_version} -> {head_version}); bump version "
                f"in plugins/{name}/{MANIFEST_RELPATH} and apm.yml, and add a "
                "matching CHANGELOG heading"
            )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Base ref to diff against (default: $GITHUB_BASE_REF, origin/main, main)",
    )
    args = parser.parse_args(argv)
    result = check_version_bumps(args.repo_root, args.base)

    if result.refusal is not None:
        print(f"ERROR: {result.refusal}", file=sys.stderr)
        return 2

    for notice in result.notices:
        print(notice)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.errors:
        print(
            f"FAIL: {len(result.errors)} version-bump problem(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: {result.changed_plugins} plugin(s) with shipped changes carry a "
        f"version bump ({result.checked_plugins} plugins checked against "
        f"{result.base_ref})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
