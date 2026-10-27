#!/usr/bin/env python3
"""Render GitHub release notes and plan which release tags are missing.

Two subcommands share one source of truth for the release convention in
``docs/releasing.md``:

``render``  Print the GitHub release body for one tag (or one plugin directory
            at its current manifest version). The body is that version's
            ``CHANGELOG.md`` section wrapped in the plugin or package template
            the hand-made releases already use, so automated and manual releases
            read the same.
``plan``    Compare every *shipped* plugin's ``plugin.json`` version with the
            tags (and optionally releases) that already exist, and say what is
            missing. Shipped means listed in ``.claude-plugin/marketplace.json``;
            an unlisted stub under ``plugins/`` is never planned.

Tag prefixes follow ``docs/releasing.md``: the plugin directory name, except a
plugin that publishes a Python package, which uses the *distribution* name
(``plugins/memory`` -> ``memorykit/v...``). Package tags are never created by
automation: pushing one triggers an irreversible PyPI upload, so ``plan`` only
reports them for a maintainer to push.

Standard library only; Python 3.10+. Exit codes: 0 = success; 1 = the inputs
were read but are wrong (unknown tag, missing changelog section, malformed
version); 2 = bad arguments (argparse).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_REPO = "mbeacom/context-kit"

# Plugin directory -> Python distribution it publishes. Keep in step with the
# `release-<distribution>.yml` workflows and the table in docs/releasing.md.
PACKAGES = {
    "indexkit": "indexkit",
    "memory": "memorykit",
}

# Versions end up in tag names, release titles, and shell variables in CI, so
# they are held to a strict shape rather than trusted as free text.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.]?(?:a|b|rc|dev|post)\.?\d+)*$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PLUGIN_TEMPLATE = """\
## Changes in {version}

{changes}

## Install

```bash
copilot plugin marketplace add {repo}
copilot plugin install {name}@{marketplace}
```

In Claude Code: `/plugin marketplace add {repo}`, then `/plugin install {name}@{marketplace}`.
"""

PACKAGE_TEMPLATE = """\
```bash
pip install {package}=={version}          # or: uv tool install {package}=={version}
```

## Changes in {version}

{changes}

## Provenance

Published via Trusted Publishing (OIDC) with PEP 740 attestations for both
artifacts. Verify with the per-file integrity endpoint — PyPI's JSON API
reports `provenance: null` for every file regardless of whether it is attested:

```bash
set -o pipefail
for file in {package}-{version}-py3-none-any.whl {package}-{version}.tar.gz; do
  curl -fsS -H 'Accept: application/vnd.pypi.integrity.v1+json' \\
    "https://pypi.org/integrity/{package}/{version}/${{file}}/provenance" \\
    | jq -e '.attestation_bundles[0].publisher | {{repository, workflow}}'
done
```

Both report `{repo}` / `release-{package}.yml`.
"""


class ReleaseError(Exception):
    """The inputs were readable but do not describe a valid release."""


@dataclass(frozen=True)
class Plugin:
    name: str
    directory: str
    version: str
    package: str | None

    @property
    def prefix(self) -> str:
        return self.package or self.name

    @property
    def tag(self) -> str:
        return f"{self.prefix}/v{self.version}"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReleaseError(f"cannot read {path}: {exc}") from exc


def load_marketplace(root: Path) -> tuple[str, list[str]]:
    """Return the marketplace name and the shipped plugin directory names."""
    data = _load_json(root / ".claude-plugin" / "marketplace.json")
    directories = []
    for entry in data.get("plugins", []):
        source = entry.get("source")
        if not isinstance(source, str):
            raise ReleaseError(f"plugin {entry.get('name')!r} has no path source")
        source_path = Path(source)
        if source_path.parent != Path("plugins") and source_path.parent != Path(
            "./plugins"
        ):
            raise ReleaseError(f"unexpected plugin source {source!r}")
        directories.append(source_path.name)
    return data["name"], directories


def load_plugin(root: Path, directory: str) -> Plugin:
    manifest = _load_json(
        root / "plugins" / directory / ".claude-plugin" / "plugin.json"
    )
    name = manifest.get("name", "")
    version = manifest.get("version", "")
    if not NAME_RE.match(name):
        raise ReleaseError(f"plugins/{directory}: invalid plugin name {name!r}")
    if not VERSION_RE.match(version):
        raise ReleaseError(f"plugins/{directory}: invalid version {version!r}")
    return Plugin(
        name=name, directory=directory, version=version, package=PACKAGES.get(directory)
    )


def shipped_plugins(root: Path) -> list[Plugin]:
    _, directories = load_marketplace(root)
    return [load_plugin(root, directory) for directory in directories]


def changelog_section(changelog: Path, version: str) -> str:
    """Return the body of the ``## <version>`` section, without its heading."""
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseError(f"cannot read {changelog}: {exc}") from exc
    # The version must be followed by whitespace or end of line, so 0.6.6 can
    # never select a 0.6.60 or 0.6.6rc1 section.
    heading = re.compile(
        rf"^##[ \t]+v?{re.escape(version)}(?=[ \t]|$).*$", re.MULTILINE
    )
    match = heading.search(text)
    if match is None:
        raise ReleaseError(f"{changelog}: no '## {version}' section")
    following = re.compile(r"^## ", re.MULTILINE).search(text, match.end())
    body = text[match.end() : following.start() if following else len(text)]
    body = body.strip("\n").rstrip()
    if not body.strip():
        raise ReleaseError(f"{changelog}: the '## {version}' section is empty")
    return body


def resolve_tag(root: Path, tag: str) -> tuple[Plugin, str]:
    """Map ``<prefix>/v<version>`` to its shipped plugin and the tagged version."""
    prefix, sep, version = tag.partition("/v")
    if not sep or not VERSION_RE.match(version):
        raise ReleaseError(f"tag {tag!r} is not <prefix>/v<version>")
    for plugin in shipped_plugins(root):
        if plugin.prefix == prefix:
            return plugin, version
    raise ReleaseError(f"tag prefix {prefix!r} names no shipped plugin or package")


def render(root: Path, plugin: Plugin, version: str, repo: str) -> str:
    marketplace, _ = load_marketplace(root)
    changes = changelog_section(
        root / "plugins" / plugin.directory / "CHANGELOG.md", version
    )
    if plugin.package:
        return PACKAGE_TEMPLATE.format(
            package=plugin.package, version=version, changes=changes, repo=repo
        )
    return PLUGIN_TEMPLATE.format(
        name=plugin.name,
        version=version,
        changes=changes,
        repo=repo,
        marketplace=marketplace,
    )


def _read_names(path: str | None) -> set[str] | None:
    if path is None:
        return None
    if path == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ReleaseError(f"cannot read {path}: {exc}") from exc
    return {line.strip() for line in text.splitlines() if line.strip()}


def _git_tags(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "tag", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError(f"git tag --list failed: {result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def plan(root: Path, tags: set[str], releases: set[str] | None) -> list[dict]:
    """One entry per shipped plugin, each with the action automation should take.

    ``tag-and-release``  non-package plugin whose tag is missing.
    ``release``          non-package plugin tagged but without a GitHub release
                         (only knowable when ``releases`` is given) - repairs a
                         run that pushed the tag and then failed.
    ``maintainer-tag``   package plugin whose tag is missing; a human must push
                         it, because the tag push publishes to PyPI.
    ``none``             nothing to do.
    """
    entries = []
    for plugin in shipped_plugins(root):
        tag_exists = plugin.tag in tags
        release_exists = None if releases is None else plugin.tag in releases
        if plugin.package:
            action = "none" if tag_exists else "maintainer-tag"
        elif not tag_exists:
            action = "tag-and-release"
        elif release_exists is False:
            action = "release"
        else:
            action = "none"
        entry = asdict(plugin)
        entry.update(
            prefix=plugin.prefix,
            tag=plugin.tag,
            tag_exists=tag_exists,
            release_exists=release_exists,
            action=action,
        )
        entries.append(entry)
    return entries


def _format_plan(entries: list[dict], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(entries, indent=2) + "\n"
    actionable = [entry for entry in entries if entry["action"] != "none"]
    if fmt == "tsv":
        # action, tag, plugin directory, title - one actionable row per line,
        # for a `while IFS=$'\t' read` loop in CI.
        return "".join(
            f"{e['action']}\t{e['tag']}\t{e['directory']}\t{e['prefix']} {e['version']}\n"
            for e in actionable
        )
    if not actionable:
        return "Every shipped plugin version is tagged.\n"
    return "".join(f"{e['action']:<16} {e['tag']}\n" for e in actionable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: this script's repository)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    render_parser = sub.add_parser("render", help="print one release body")
    target = render_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--tag", help="release tag, e.g. verify/v0.5.8")
    target.add_argument(
        "--plugin-dir", help="plugin directory, rendered at its plugin.json version"
    )
    render_parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/name")
    render_parser.add_argument(
        "--output", type=Path, help="write here instead of stdout"
    )

    plan_parser = sub.add_parser("plan", help="list missing release tags")
    plan_parser.add_argument(
        "--existing-tags-file",
        help="tag names, one per line ('-' for stdin); default: git tag --list",
    )
    plan_parser.add_argument(
        "--existing-releases-file",
        help="tag names that already have a GitHub release, one per line",
    )
    plan_parser.add_argument(
        "--format", choices=("text", "json", "tsv"), default="text"
    )

    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "render":
            if args.tag:
                plugin, version = resolve_tag(root, args.tag)
            else:
                plugin = load_plugin(root, Path(args.plugin_dir).name)
                version = plugin.version
            body = render(root, plugin, version, args.repo)
            if args.output:
                args.output.write_text(body, encoding="utf-8")
            else:
                sys.stdout.write(body)
        else:
            tags = _read_names(args.existing_tags_file)
            if tags is None:
                tags = _git_tags(root)
            releases = _read_names(args.existing_releases_file)
            sys.stdout.write(_format_plan(plan(root, tags, releases), args.format))
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
