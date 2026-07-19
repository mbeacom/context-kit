#!/usr/bin/env bash
# Validate cross-plugin discovery metadata using only Python's standard library.
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for the catalog quality gate" >&2
  exit 2
fi

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [repo-root]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"

python3 "${SCRIPT_DIR}/catalog_quality.py" "$REPO_ROOT"
