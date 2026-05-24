---
name: retrieval-strategy
description: "Use when deciding HOW to find information — choosing or composing search modalities (lexical, structural, structured-data, history, semantic/RAG, graph) for a query and corpus."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Glob Grep Bash
---

# Retrieval Strategy

Pick a modality by **what you know about the query × what you know about the corpus.**

## Decision flow

- Know the exact token / regex / filename? → **lexical** (`rg`, `fd`)
- Know the code *shape*, not the text? → **structural** (`ast-grep`, `semgrep`)
- Querying JSON / YAML / config by schema? → **structured-data** (`jq`, `yq`, `gron`)
- Asking *when/why* something changed? → **history** (`git log -S/-G/-L`)
- Tabular data at scale (CSV/Parquet)? → **data files** (`duckdb`, `sqlite-utils`)
- Sizing / complexity of a codebase? → **metrics** (`tokei`, `scc`)
- Content inside PDFs / Office docs / archives? → **docs** (`rga`, `pandoc`)
- Only know the *meaning/intent*, or corpus is huge / unfamiliar / prose? →
  **semantic / RAG** (`local-rag`: turbovec + ollama)
- Corpus is a human-authored link graph? → **graph** (`obsidian`)

Lexical/structural/structured-data/history/metrics/docs live in **code-search**.
Semantic and graph live in **local-rag** and **obsidian** (install separately).

## Composition (modalities are layers, not rivals)

- **Hybrid rerank:** lexical or structured-data produces a candidate set →
  semantic reranks it (turbovec search with an `allowlist` of candidate ids).
- **Scope then search:** graph backlinks narrow to a subgraph → RAG within it.
- **Find then pin:** RAG surfaces candidate regions → `rg` pins exact lines.

## Defaults

1. Start with the cheapest modality that fits (lexical is free and instant).
2. Narrow before widening; count matches (`rg -c`) before reading full output.
3. Escalate to semantic only when lexical/structural genuinely can't express the
   query (intent without known terms) or the corpus is too large/unfamiliar.
4. If a needed plugin (`local-rag`, `obsidian`) isn't installed, say so and
   suggest installing it — don't assume its tools exist.
