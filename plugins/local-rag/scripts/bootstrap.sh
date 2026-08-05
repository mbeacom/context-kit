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
# CONTEXT_KIT_DATA locates *index data*; CONTEXT_KIT_LOCAL_RAG_HOME locates the
# venv. They are the same directory by default. Keeping the seam explicit lets a
# caller redirect index data (for project isolation) without relocating the venv.
DATA="${CONTEXT_KIT_DATA:-${PRODUCTIVITY_SKILLS_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/local-rag}}}"
HOME_DIR="${CONTEXT_KIT_LOCAL_RAG_HOME:-$DATA}"
VENV="$HOME_DIR/venv"
STAMP="$HOME_DIR/pyproject.sha"
SRC_PROJECT="$PLUGIN_ROOT/pyproject.toml"

report() {
  # report <status> [detail]
  printf 'status=%s\n' "$1"
  printf 'home=%s\n' "$HOME_DIR"
  printf 'venv=%s\n' "$VENV"
  printf 'plugin_root=%s\n' "$PLUGIN_ROOT"
  printf 'bootstrap_command=bash %s/scripts/bootstrap.sh\n' "$PLUGIN_ROOT"
  if [[ -n "${2:-}" ]]; then
    printf 'detail=%s\n' "$2"
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  if (( CHECK_ONLY )); then
    report uv-missing "install uv: https://docs.astral.sh/uv/"
    exit 3
  fi
  echo "local-rag: 'uv' not found. Install uv: https://docs.astral.sh/uv/ " >&2
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
  if [[ ! -x "$VENV/bin/python" ]]; then
    report missing "no interpreter at $VENV/bin/python"
    exit 3
  fi
  if [[ "$cur_sha" != "$old_sha" ]]; then
    # A venv built from different project metadata runs stale code silently,
    # so this is reported as loudly as a missing one.
    report stale "venv was built from different pyproject.toml metadata"
    exit 3
  fi
  report ready
  exit 0
fi

mkdir -p "$HOME_DIR"
if [[ ! -x "$VENV/bin/python" || "$cur_sha" != "$old_sha" ]]; then
  echo "local-rag: syncing venv ($VENV)..." >&2
  uv venv "$VENV" >/dev/null
  VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" "$PLUGIN_ROOT" >/dev/null
  echo "$cur_sha" > "$STAMP"
fi
echo "local-rag: venv ready at $VENV" >&2
