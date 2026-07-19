#!/usr/bin/env bash
# check-tools.sh — report which code-search CLI tools are installed.
set -euo pipefail

# tool|purpose|brew formula
TOOLS=(
  "rg|lexical text search (required)|ripgrep"
  "fd|file finder|fd"
  "sg|structural search (ast-grep)|ast-grep"
  "semgrep|rule packs / taint|semgrep"
  "git|history / pickaxe (required)|git"
  "comby|structural rewrite|comby"
  "difft|structural diffs (difftastic)|difftastic"
  "tokei|LOC metrics|tokei"
  "scc|complexity metrics|scc"
  "ctags|symbol definitions (universal-ctags)|universal-ctags"
  "global|symbol defs+references (GNU Global)|global"
  "jq|JSON query|jq"
  "yq|YAML/TOML/XML query|yq"
  "gron|greppable JSON|gron"
  "duckdb|SQL over data files|duckdb"
  "sqlite-utils|SQLite/CSV query|sqlite-utils"
  "rga|search PDFs/Office/archives|ripgrep-all"
  "pandoc|document conversion|pandoc"
  "pdftotext|PDF text extraction|poppler"
)

missing=()
printf "%-14s %-34s %s\n" "TOOL" "PURPOSE" "STATUS"
printf "%-14s %-34s %s\n" "----" "-------" "------"
for entry in "${TOOLS[@]}"; do
  IFS='|' read -r tool purpose formula <<<"$entry"
  if command -v "$tool" >/dev/null 2>&1; then
    printf "%-14s %-34s %s\n" "$tool" "$purpose" "present"
  else
    printf "%-14s %-34s %s\n" "$tool" "$purpose" "MISSING (brew install $formula)"
    missing+=("$formula")
  fi
done

# rtk is an optional token-saving proxy (rtk-ai/rtk), not a brew formula —
# report it but never count it toward the missing/exit-1 path.
if command -v rtk >/dev/null 2>&1; then
  printf "%-14s %-34s %s\n" "rtk" "token-saving CLI proxy (optional)" "present"
else
  printf "%-14s %-34s %s\n" "rtk" "token-saving CLI proxy (optional)" "absent (github.com/rtk-ai/rtk)"
fi

if ((${#missing[@]})); then
  echo ""
  uniq_formulas=$(printf "%s\n" "${missing[@]}" | sort -u | tr '\n' ' ')
  echo "Install missing tools: brew install ${uniq_formulas}"
  exit 1
fi
echo ""
echo "All code-search tools present."
