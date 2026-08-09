#!/usr/bin/env bash
# Idempotent uv-based venv bootstrap into the plugin data dir.
#
# Usage:
#   bootstrap.sh            install or re-sync the venv when needed
#   bootstrap.sh --check    report readiness only; never installs
#
# `--check` prints KEY=VALUE lines (not JSON, so there are no escaping
# concerns) and exits 0 when ready, 3 when a bootstrap is required. It is what
# lets a dependent plugin detect a missing or stale venv on hosts that do not
# run the Claude SessionStart hook, such as GitHub Copilot and APM.
set -euo pipefail

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "") ;;
  *)
    echo "usage: bootstrap.sh [--check]" >&2
    exit 2
    ;;
esac

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# CONTEXT_KIT_DATA locates *index data*; CONTEXT_KIT_INDEXKIT_HOME locates the
# venv. They are the same directory by default. Keeping the seam explicit lets a
# caller redirect index data (for project isolation) without relocating the venv.
# CONTEXT_KIT_LOCAL_RAG_HOME is the pre-rename name (ADR-0007), still honored.
DATA="${CONTEXT_KIT_DATA:-${PRODUCTIVITY_SKILLS_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/indexkit}}}"
HOME_DIR="${CONTEXT_KIT_INDEXKIT_HOME:-${CONTEXT_KIT_LOCAL_RAG_HOME:-$DATA}}"
VENV="$HOME_DIR/venv"
STAMP="$HOME_DIR/pyproject.sha"
SRC_PROJECT="$PLUGIN_ROOT/pyproject.toml"

report() {
  # report <status> <venv_status> [detail]
  # `status` is the actionable answer; `venv_status` is the raw venv state,
  # which stays accurate even when uv is unavailable to rebuild it.
  printf 'status=%s\n' "$1"
  printf 'venv_status=%s\n' "$2"
  printf 'uv=%s\n' "$HAVE_UV"
  printf 'home=%s\n' "$HOME_DIR"
  printf 'venv=%s\n' "$VENV"
  printf 'plugin_root=%s\n' "$PLUGIN_ROOT"
  printf 'bootstrap_command=bash %s/scripts/bootstrap.sh\n' "$PLUGIN_ROOT"
  if [[ -n "${3:-}" ]]; then
    printf 'detail=%s\n' "$3"
  fi
}

HAVE_UV=present
command -v uv >/dev/null 2>&1 || HAVE_UV=missing

if [[ "$HAVE_UV" == missing && $CHECK_ONLY -eq 0 ]]; then
  echo "indexkit: 'uv' not found. Install uv: https://docs.astral.sh/uv/ " >&2
  exit 1
fi

# sha256sum on Linux, shasum on macOS — prefer whichever exists.
if command -v sha256sum >/dev/null 2>&1; then
  cur_sha="$(sha256sum "$SRC_PROJECT" | awk '{print $1}')"
else
  cur_sha="$(shasum -a 256 "$SRC_PROJECT" | awk '{print $1}')"
fi
old_sha="$(cat "$STAMP" 2>/dev/null || true)"

if (( CHECK_ONLY )); then
  # Venv state is decided first. A usable venv needs no uv, so reporting
  # "uv-missing" for a working runtime would be wrong.
  if [[ ! -x "$VENV/bin/python" ]]; then
    venv_status=missing
    detail="no interpreter at $VENV/bin/python"
  elif [[ "$cur_sha" != "$old_sha" ]]; then
    # A venv built from different project metadata runs stale code silently,
    # so this is reported as loudly as a missing one.
    venv_status=stale
    detail="venv was built from different pyproject.toml metadata"
  else
    report ready ready
    exit 0
  fi
  # Only an unusable venv actually needs uv, and then it is the first blocker.
  if [[ "$HAVE_UV" == missing ]]; then
    report uv-missing "$venv_status" "$detail; and uv is not installed: https://docs.astral.sh/uv/"
    exit 3
  fi
  report "$venv_status" "$venv_status" "$detail"
  exit 3
fi

mkdir -p "$HOME_DIR"
if [[ ! -x "$VENV/bin/python" || "$cur_sha" != "$old_sha" ]]; then
  echo "indexkit: syncing venv ($VENV)..." >&2
  uv venv "$VENV" >/dev/null
  VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" "$PLUGIN_ROOT" >/dev/null
  echo "$cur_sha" > "$STAMP"
fi
echo "indexkit: venv ready at $VENV" >&2
