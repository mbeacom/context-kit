#!/usr/bin/env bash
# check-skills.sh — validate the discovery frontmatter of every skill and agent.
#
# GitHub Copilot and Claude Code both decide WHEN to load a skill or subagent
# from its `name` + `description` frontmatter. A missing, malformed, mis-named,
# or empty description silently breaks discovery — the component ships but never
# fires. This asserts every SKILL.md and agents/*.md carries a present,
# well-formed, discovery-optimized `name` and `description`.
#
# Checks (all fatal):
#   - has YAML frontmatter (opening + closing `---`)
#   - `name` present, kebab-case, and equal to the skill dir / agent file name
#   - `description` present, 40..1024 chars, and trigger-phrased ("Use …")
#
# Run from any working directory; pass an explicit plugins dir as $1 to override.
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to parse skill/agent frontmatter" >&2
  exit 2
fi

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [plugins-dir]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -eq 1 ]; then
  if [ ! -d "$1" ]; then
    echo "ERROR: plugins dir not found: $1" >&2
    exit 2
  fi
  PLUGINS_DIR="$(cd "$1" && pwd)"
else
  # This script lives at plugins/plugin-forge/scripts/check-skills.sh, so two
  # levels up (scripts/ -> plugin-forge/ -> plugins/) is the repo's plugins/ dir.
  PLUGINS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi

python3 - "$PLUGINS_DIR" <<'PY'
import os
import re
import sys

plugins_dir = sys.argv[1]
repo_dir = os.path.dirname(plugins_dir)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DESC_MIN = 40
DESC_MAX = 1024


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_frontmatter(path):
    """Return a dict of top-level scalar frontmatter fields, or None if the file
    has no opening/closing `---` fence. Nested (indented) keys are ignored; we
    only need the top-level `name` and `description` scalars."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line or line[0] in (" ", "\t") or ":" not in line:
            continue  # continuation / nested / non key:value line
        key, value = line.split(":", 1)
        fields[key.strip()] = unquote(value)
    return None  # never closed: treat as malformed


def discover(root):
    for dirpath, _dirs, files in os.walk(root):
        parts = os.path.relpath(dirpath, root).split(os.sep)
        for name in files:
            full = os.path.join(dirpath, name)
            if name == "SKILL.md" and "skills" in parts:
                yield full, os.path.basename(dirpath), "skill"
            elif name.endswith(".md") and parts[-1] == "agents" and name != "README.md":
                yield full, name[:-3], "agent"


errors = []
count = 0
for path, expected, kind in sorted(discover(plugins_dir)):
    count += 1
    label = os.path.relpath(path, repo_dir)
    fields = parse_frontmatter(path)
    if fields is None:
        errors.append(f"{label}: missing or unterminated YAML frontmatter")
        continue

    name = fields.get("name", "")
    if not name:
        errors.append(f"{label}: missing `name`")
    else:
        if not NAME_RE.match(name):
            errors.append(f"{label}: name '{name}' is not kebab-case ([a-z0-9-])")
        if name != expected:
            errors.append(
                f"{label}: name '{name}' does not match {kind} name '{expected}'"
            )

    desc = fields.get("description", "")
    if not desc:
        errors.append(f"{label}: missing `description`")
    else:
        length = len(desc)
        if length < DESC_MIN:
            errors.append(f"{label}: description too short ({length} < {DESC_MIN} chars)")
        if length > DESC_MAX:
            errors.append(f"{label}: description too long ({length} > {DESC_MAX} chars)")
        if not desc.lower().startswith("use "):
            errors.append(
                f'{label}: description should start with a trigger, e.g. "Use when …"'
            )

for message in errors:
    print(f"ERROR: {message}", file=sys.stderr)

if errors:
    print(
        f"\nFAIL: {len(errors)} problem(s) across {count} skill/agent file(s)",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"OK: {count} skills/agents, discovery frontmatter valid")
PY
