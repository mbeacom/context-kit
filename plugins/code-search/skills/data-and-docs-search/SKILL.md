---
name: data-and-docs-search
description: "Use when searching non-code corpora: query JSON/YAML/config (jq, yq, gron), tabular data files (duckdb, sqlite-utils), or content inside PDFs/Office docs/archives (rga, pandoc, pdftotext)."
license: MIT
compatibility: "Optional tools: jq, yq, gron, duckdb, sqlite-utils, rga (ripgrep-all), pandoc, pdftotext."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(jq:*) Bash(yq:*) Bash(gron:*) Bash(duckdb:*) Bash(sqlite-utils:*) Bash(rga:*) Bash(pandoc:*) Bash(pdftotext:*) Bash(rg:*) Read Glob Grep
---

# Data & Docs Search

Search beyond source code.

| Corpus                         | Use                       | Reference                          |
| ------------------------------ | ------------------------- | ---------------------------------- |
| JSON                           | `jq`, or `gron` + `rg`    | [jq-yq-gron](references/jq-yq-gron.md) |
| YAML / TOML / XML              | `yq`                      | [jq-yq-gron](references/jq-yq-gron.md) |
| CSV / Parquet / JSON at scale  | `duckdb`, `sqlite-utils`  | [data-files](references/data-files.md) |
| PDFs / Office docs / archives  | `rga`, `pandoc`, `pdftotext` | [docs](references/docs.md)      |

**Decision flow:** known JSON path → `jq` | "grep this JSON" → `gron \| rg` |
YAML/TOML → `yq` | tabular/analytical → `duckdb` | inside PDFs/docs → `rga`.

## Best practices

1. `gron file.json | rg pattern` turns nested JSON into greppable lines — ideal
   when you don't know the exact path. `gron -u` reverses it.
2. `rga` is `rg` for non-text files; first run builds a cache, later runs are fast.
   Scope with `--rga-adapters` and the same globs as `rg`.
3. For analytical queries over CSV/Parquet, `duckdb` reads files directly:
   `duckdb -c "SELECT ... FROM 'data.parquet' ..."`.
4. These tools are optional — run `scripts/check-tools.sh` and install what's
   missing before relying on them.
