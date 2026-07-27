#!/usr/bin/env bash
# Fail when shipped plugin content changed without a version bump (CI-only gate).
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for the version-bump gate" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${SCRIPT_DIR}/version_bump.py" "$@"
