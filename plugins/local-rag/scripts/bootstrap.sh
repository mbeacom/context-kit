#!/usr/bin/env bash
# Idempotent uv-based venv bootstrap into the plugin data dir.
set -euo pipefail
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/local-rag}"
mkdir -p "$DATA"
VENV="$DATA/venv"
STAMP="$DATA/pyproject.sha"
SRC_PROJECT="$PLUGIN_ROOT/pyproject.toml"

if ! command -v uv >/dev/null 2>&1; then
  echo "local-rag: 'uv' not found. Install uv: https://docs.astral.sh/uv/ " >&2
  exit 1
fi

cur_sha="$(shasum -a 256 "$SRC_PROJECT" | awk '{print $1}')"
old_sha="$(cat "$STAMP" 2>/dev/null || true)"
if [[ ! -x "$VENV/bin/python" || "$cur_sha" != "$old_sha" ]]; then
  echo "local-rag: syncing venv ($VENV)..." >&2
  uv venv "$VENV" >/dev/null
  VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" "$PLUGIN_ROOT" >/dev/null
  echo "$cur_sha" > "$STAMP"
fi
echo "local-rag: venv ready at $VENV" >&2
