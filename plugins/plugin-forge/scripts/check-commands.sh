#!/usr/bin/env bash
# check-commands.sh — validate the YAML frontmatter of every slash command.
#
# A command whose frontmatter field resolves to the wrong YAML type fails to
# load outright (e.g. an unquoted `argument-hint: [path]` is a flow sequence,
# so the host reports `argument-hint must be a string`). check-skills.sh covers
# only skills and agents, so this closes the commands/ gap.
#
# Run from any working directory; pass an explicit plugins dir as $1 to override.
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to parse command frontmatter" >&2
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
  # This script lives at plugins/plugin-forge/scripts/check-commands.sh, so two
  # levels up (scripts/ -> plugin-forge/ -> plugins/) is the repo's plugins/ dir.
  PLUGINS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi

python3 "${SCRIPT_DIR}/command_frontmatter.py" "$PLUGINS_DIR"
