#!/usr/bin/env bash
# Lint the repository's ADR corpus with adrkit (ADR-0001).
#
# Loose coupling is deliberate. adrkit is Apache-2.0 and Node-based, while this
# catalog ships Python-stdlib and shell plugins; it is a contributor-side tool,
# not a dependency of anything we publish. A contributor without Node must still
# be able to run `pre-commit run --all-files` to completion.
#
# So absence of the toolchain is a skip, not a failure. A toolchain that *is*
# present and reports lint errors is a failure — an absent tool tells us nothing
# about the corpus, but a present one does.
#
# Exit codes: 0 = corpus clean, or checking was skipped; 1 = lint errors.
set -euo pipefail

# Pinned: adrkit is pre-1.0 and its schema may change across minor versions.
ADRKIT_VERSION="${ADRKIT_VERSION:-0.4.0}"
ADR_DIR="${ADR_DIR:-docs/adr}"

skip() {
  echo "adr lint: skipped — $1"
  exit 0
}

[ "${ADRKIT_SKIP:-}" = "1" ] && skip "ADRKIT_SKIP=1"
[ -d "$ADR_DIR" ] || skip "no corpus at $ADR_DIR"
command -v npx >/dev/null 2>&1 || skip "npx not found (install Node 22+ to lint ADRs)"

# `adr` on PATH wins: it is faster than npx and lets a contributor pin their own
# install. Otherwise fall back to the pinned package.
if command -v adr >/dev/null 2>&1; then
  adr lint --dir "$ADR_DIR"
else
  npx --yes "@adrkit/cli@${ADRKIT_VERSION}" lint --dir "$ADR_DIR"
fi
