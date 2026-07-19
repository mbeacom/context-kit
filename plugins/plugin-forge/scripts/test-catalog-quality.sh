#!/usr/bin/env bash
# Run hermetic validator tests and the mocked workflow smoke test.
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for plugin-forge tests" >&2
  exit 2
fi
if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node is required for the workflow smoke test" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PLUGIN_DIR}/../.." && pwd)"

python3 -m unittest discover -s "${PLUGIN_DIR}/tests" -p 'test_*.py'
node "${PLUGIN_DIR}/tests/smoke-plan-workflow.mjs" \
  "${REPO_ROOT}/plugins/plan-execute/workflows/plan-big-execute-small.workflow.js"
