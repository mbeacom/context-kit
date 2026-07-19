#!/usr/bin/env bash
# Run hermetic release-readiness validator regression tests.
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for release-readiness tests" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

python3 -m unittest discover \
  -s "${PLUGIN_DIR}/tests" \
  -p 'test_release_readiness.py'
