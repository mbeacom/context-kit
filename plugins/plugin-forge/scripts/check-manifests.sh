#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to parse plugin.json manifests" >&2
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
  PLUGINS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi

json_field() {
  local file="$1"
  local field="$2"

  python3 - "$file" "$field" <<'PY'
import json
import sys

path = sys.argv[1]
field = sys.argv[2]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
value = data.get(field, "")
if not isinstance(value, str):
    value = str(value)
print(value)
PY
}

apm_field() {
  local file="$1"
  local key="$2"

  awk -F: -v key="$key" '
    $1 == key {
      value = $0
      sub("^[^:]*:[[:space:]]*", "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^["]|["]$/, "", value)
      print value
      exit
    }
  ' "$file"
}

total=0
failures=0

for plugin_dir in "${PLUGINS_DIR}"/*/; do
  [ -d "$plugin_dir" ] || continue

  plugin_json="${plugin_dir}.claude-plugin/plugin.json"
  [ -f "$plugin_json" ] || continue

  total=$((total + 1))
  plugin_label="$(basename "${plugin_dir%/}")"
  apm_yml="${plugin_dir}apm.yml"

  if [ ! -f "$apm_yml" ]; then
    echo "ERROR: ${plugin_label}: missing apm.yml" >&2
    failures=$((failures + 1))
    continue
  fi

  json_name="$(json_field "$plugin_json" name)"
  json_version="$(json_field "$plugin_json" version)"
  apm_name="$(apm_field "$apm_yml" name)"
  apm_version="$(apm_field "$apm_yml" version)"

  if [ "$json_name" != "$apm_name" ]; then
    echo "ERROR: ${plugin_label}: name mismatch (plugin.json name=${json_name} apm.yml name=${apm_name})" >&2
    failures=$((failures + 1))
  fi

  if [ "$json_version" != "$apm_version" ]; then
    echo "ERROR: ${plugin_label}: version mismatch (plugin.json version=${json_version} apm.yml version=${apm_version})" >&2
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  exit 1
fi

echo "OK: ${total} plugins, manifests in sync"
