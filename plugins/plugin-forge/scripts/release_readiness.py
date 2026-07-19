#!/usr/bin/env python3
"""Validate release readiness for every plugin shipped by the catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SEMVER_CORE_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)
RELEASE_HEADING_RE = re.compile(
    r"^##\s+(?P<version>\S+)\s+(?:—|-)\s+" r"(?P<date>\d{4}-\d{2}-\d{2})\s*$"
)
RELEASE_LIKE_RE = re.compile(r"^##\s+\d+\.\d+\.\S+")
TOP_LEVEL_YAML_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$")
APM_PATH_RE = re.compile(r"^-\s+path:\s*(.+?)\s*$")
REQUIRED_ASSETS = ("README.md", "CHANGELOG.md", "LICENSE", "apm.yml")
REQUIRED_APM_FIELDS = (
    "name",
    "version",
    "description",
    "author",
    "license",
    "homepage",
    "repository",
    "keywords",
)
COMPONENT_PATHS = (
    "skills",
    "agents",
    "commands",
    "scripts",
    "hooks",
    "workflows",
    "bin",
)


@dataclass
class PluginRecord:
    name: str
    directory: Path
    manifest: dict[str, Any]
    json_dependencies: list[str]
    apm_dependency_paths: list[str]


@dataclass
class ValidationResult:
    errors: list[str]
    plugin_count: int = 0
    dependency_edge_count: int = 0


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot load JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}: top level must be an object")
        return {}
    return data


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _yaml_scalar(value: str) -> str:
    value = re.sub(r"\s+#.*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _is_semver(value: str) -> bool:
    match = SEMVER_CORE_RE.fullmatch(value)
    if match is None:
        return False
    prerelease = match.group(4)
    build = match.group(5)
    for section in (prerelease, build):
        if section is None:
            continue
        identifiers = section.split(".")
        if any(
            not identifier or re.fullmatch(r"[0-9A-Za-z-]+", identifier) is None
            for identifier in identifiers
        ):
            return False
    if prerelease is not None:
        for identifier in prerelease.split("."):
            if (
                identifier.isdigit()
                and len(identifier) > 1
                and identifier.startswith("0")
            ):
                return False
    return True


def _parse_apm(
    path: Path, label: str, errors: list[str]
) -> tuple[dict[str, str], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"{label}: cannot read: {exc}")
        return {}, []

    fields: dict[str, str] = {}
    dependency_paths: list[str] = []
    in_dependencies = False
    in_apm = False
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            match = TOP_LEVEL_YAML_RE.fullmatch(stripped)
            in_dependencies = bool(match and match.group(1) == "dependencies")
            in_apm = False
            if match:
                fields[match.group(1)] = _yaml_scalar(match.group(2) or "")
            continue
        if not in_dependencies:
            continue
        if indent == 2:
            in_apm = stripped == "apm:"
            continue
        if in_apm and indent == 4 and stripped.startswith("-"):
            match = APM_PATH_RE.fullmatch(stripped)
            if match is None:
                errors.append(
                    f"{label}:{line_number}: dependencies.apm entries must use "
                    "`- path: ../<plugin>`"
                )
                continue
            dependency_paths.append(_yaml_scalar(match.group(1)))
        elif in_apm and indent >= 4:
            errors.append(
                f"{label}:{line_number}: dependencies.apm must contain only "
                "direct `- path: ../<plugin>` entries"
            )
    return fields, dependency_paths


def _required_string(
    mapping: dict[str, Any], key: str, label: str, errors: list[str]
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: `{key}` must be a non-empty string")
        return ""
    return value.strip()


def _validate_manifest_metadata(
    manifest: dict[str, Any], label: str, errors: list[str]
) -> None:
    for key in (
        "$schema",
        "name",
        "displayName",
        "version",
        "description",
        "homepage",
        "repository",
        "license",
    ):
        _required_string(manifest, key, label, errors)

    author = manifest.get("author")
    if not isinstance(author, dict):
        errors.append(f"{label}: `author` must be an object")
    else:
        _required_string(author, "name", f"{label}: author", errors)

    keywords = manifest.get("keywords")
    if (
        not isinstance(keywords, list)
        or not keywords
        or not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords)
    ):
        errors.append(f"{label}: `keywords` must be a non-empty array of strings")

    version = manifest.get("version")
    if isinstance(version, str) and not _is_semver(version):
        errors.append(f"{label}: version `{version}` is not semantic versioning")


def _validate_apm_metadata(
    manifest: dict[str, Any],
    fields: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    for key in REQUIRED_APM_FIELDS:
        if not fields.get(key):
            errors.append(f"{label}: missing top-level `{key}` metadata")

    author = manifest.get("author")
    manifest_author = author.get("name") if isinstance(author, dict) else None
    for key, manifest_value in (
        ("author", manifest_author),
        ("license", manifest.get("license")),
        ("homepage", manifest.get("homepage")),
        ("repository", manifest.get("repository")),
    ):
        apm_value = fields.get(key)
        if (
            isinstance(manifest_value, str)
            and apm_value
            and manifest_value != apm_value
        ):
            errors.append(
                f"{label}: `{key}` differs from plugin.json "
                f"({apm_value!r} != {manifest_value!r})"
            )


def _validate_changelog(
    path: Path, version: str, label: str, errors: list[str]
) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"{label}: cannot read: {exc}")
        return

    release_line = next((line for line in lines if RELEASE_LIKE_RE.match(line)), None)
    if release_line is None:
        errors.append(
            f"{label}: no release heading like `## {version} — YYYY-MM-DD` found"
        )
        return
    match = RELEASE_HEADING_RE.fullmatch(release_line)
    if match is None or not _is_semver(match.group("version")):
        errors.append(f"{label}: malformed latest release heading `{release_line}`")
        return
    changelog_version = match.group("version")
    if changelog_version != version:
        errors.append(
            f"{label}: latest release is {changelog_version}, "
            f"but plugin.json is {version}"
        )
    try:
        date.fromisoformat(match.group("date"))
    except ValueError:
        errors.append(f"{label}: release date `{match.group('date')}` is invalid")


def _has_component(directory: Path) -> bool:
    if (directory / ".mcp.json").is_file():
        return True
    return any(
        child.is_file()
        for name in COMPONENT_PATHS
        if (component_dir := directory / name).is_dir()
        for child in component_dir.rglob("*")
    )


def _json_dependencies(
    manifest: dict[str, Any], label: str, errors: list[str]
) -> list[str]:
    value = manifest.get("dependencies", [])
    if not isinstance(value, list) or not all(
        isinstance(dependency, str) and dependency for dependency in value
    ):
        errors.append(f"{label}: `dependencies` must be an array of plugin names")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label}: `dependencies` contains duplicates")
    return list(value)


def _dependency_closure(graph: dict[str, set[str]], start: str) -> set[str]:
    closure: set[str] = set()
    pending = list(graph.get(start, set()))
    while pending:
        dependency = pending.pop()
        if dependency == start or dependency in closure:
            continue
        closure.add(dependency)
        pending.extend(graph.get(dependency, set()))
    return closure


def _find_cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
        body = nodes[:-1]
        rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
        canonical = min(rotations)
        return (*canonical, canonical[0])

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dependency in sorted(graph.get(node, set())):
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state.get(dependency) == 1:
                index = stack.index(dependency)
                cycles.add(canonical_cycle(stack[index:] + [dependency]))
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            visit(node)
    return sorted(cycles)


def validate_repository(repo_root: Path) -> ValidationResult:
    repo_root = repo_root.resolve()
    plugins_root = (repo_root / "plugins").resolve()
    catalog_path = repo_root / ".claude-plugin/marketplace.json"
    errors: list[str] = []
    catalog = _load_json(catalog_path, ".claude-plugin/marketplace.json", errors)
    entries = catalog.get("plugins")
    if not isinstance(entries, list):
        errors.append("catalog: `plugins` must be an array")
        return ValidationResult(errors)

    records: dict[str, PluginRecord] = {}
    records_by_directory: dict[Path, PluginRecord] = {}
    seen_sources: set[Path] = set()
    for index, entry in enumerate(entries):
        entry_label = f"catalog: plugins[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{entry_label} must be an object")
            continue
        name = _required_string(entry, "name", entry_label, errors)
        source = _required_string(entry, "source", entry_label, errors)
        if not name or not source:
            continue
        if name in records:
            errors.append(f"{entry_label}: duplicate plugin name `{name}`")
            continue

        source_path = Path(source)
        if source_path.is_absolute():
            errors.append(f"{entry_label}: source must be repository-relative")
            continue
        directory = (repo_root / source_path).resolve()
        if not _inside(directory, plugins_root) or directory.parent != plugins_root:
            errors.append(
                f"{entry_label}: source must resolve directly under `plugins/`"
            )
            continue
        if directory in seen_sources:
            errors.append(f"{entry_label}: duplicate source `{source}`")
            continue
        seen_sources.add(directory)
        if not directory.is_dir():
            errors.append(f"{entry_label}: source directory does not exist: `{source}`")
            continue

        plugin_label = f"plugin `{name}`"
        for asset in REQUIRED_ASSETS:
            asset_path = directory / asset
            if not asset_path.is_file() or asset_path.stat().st_size == 0:
                errors.append(f"{plugin_label}: missing or empty `{asset}`")
        if not _has_component(directory):
            errors.append(f"{plugin_label}: no shippable component files found")

        manifest_path = directory / ".claude-plugin/plugin.json"
        manifest = _load_json(manifest_path, f"{plugin_label}: plugin.json", errors)
        if not manifest:
            continue
        _validate_manifest_metadata(manifest, f"{plugin_label}: plugin.json", errors)
        manifest_name = manifest.get("name")
        if manifest_name != name:
            errors.append(
                f"{plugin_label}: catalog name differs from plugin.json "
                f"({name!r} != {manifest_name!r})"
            )
        if directory.name != name:
            errors.append(
                f"{plugin_label}: source directory must be named `{name}`, "
                f"not `{directory.name}`"
            )

        apm_fields, apm_dependency_paths = _parse_apm(
            directory / "apm.yml", f"{plugin_label}: apm.yml", errors
        )
        _validate_apm_metadata(manifest, apm_fields, f"{plugin_label}: apm.yml", errors)
        version = manifest.get("version")
        if isinstance(version, str):
            _validate_changelog(
                directory / "CHANGELOG.md",
                version,
                f"{plugin_label}: CHANGELOG.md",
                errors,
            )
        record = PluginRecord(
            name=name,
            directory=directory,
            manifest=manifest,
            json_dependencies=_json_dependencies(
                manifest, f"{plugin_label}: plugin.json", errors
            ),
            apm_dependency_paths=apm_dependency_paths,
        )
        records[name] = record
        records_by_directory[directory] = record

    json_graph: dict[str, set[str]] = {}
    apm_graph: dict[str, set[str]] = {}
    for name, record in sorted(records.items()):
        json_dependencies = set(record.json_dependencies)
        json_graph[name] = {
            dependency for dependency in json_dependencies if dependency in records
        }
        for dependency in sorted(json_dependencies - records.keys()):
            errors.append(
                f"plugin `{name}`: plugin.json dependency `{dependency}` "
                "is not a shipped catalog plugin"
            )

        apm_dependencies: list[str] = []
        for raw_path in record.apm_dependency_paths:
            dependency_path = Path(raw_path)
            if dependency_path.is_absolute():
                errors.append(
                    f"plugin `{name}`: APM dependency path must be relative: "
                    f"`{raw_path}`"
                )
                continue
            resolved = (record.directory / dependency_path).resolve()
            dependency = records_by_directory.get(resolved)
            if dependency is None:
                errors.append(
                    f"plugin `{name}`: APM dependency `{raw_path}` does not resolve "
                    "to a shipped catalog plugin"
                )
                continue
            apm_dependencies.append(dependency.name)
        if len(apm_dependencies) != len(set(apm_dependencies)):
            errors.append(f"plugin `{name}`: APM dependencies contain duplicates")
        apm_graph[name] = set(apm_dependencies)
        if json_dependencies != apm_graph[name]:
            errors.append(
                f"plugin `{name}`: dependency mismatch "
                f"(plugin.json={sorted(json_dependencies)!r}, "
                f"apm.yml={sorted(apm_graph[name])!r})"
            )

    for graph_name, graph in (("plugin.json", json_graph), ("apm.yml", apm_graph)):
        for cycle in _find_cycles(graph):
            errors.append(
                f"{graph_name}: dependency cycle detected: {' -> '.join(cycle)}"
            )

    for name in sorted(records):
        json_closure = _dependency_closure(json_graph, name)
        apm_closure = _dependency_closure(apm_graph, name)
        if json_closure != apm_closure:
            errors.append(
                f"plugin `{name}`: dependency closure mismatch "
                f"(plugin.json={sorted(json_closure)!r}, "
                f"apm.yml={sorted(apm_closure)!r})"
            )

    return ValidationResult(
        errors=errors,
        plugin_count=len(records),
        dependency_edge_count=sum(len(edges) for edges in json_graph.values()),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    args = parser.parse_args(argv)
    result = validate_repository(args.repo_root)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.errors:
        print(
            f"FAIL: {len(result.errors)} release-readiness problem(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: {result.plugin_count} shipped plugins release-ready; "
        f"{result.dependency_edge_count} dependency edges consistent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
