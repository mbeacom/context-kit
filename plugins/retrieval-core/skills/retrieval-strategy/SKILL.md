---
name: retrieval-strategy
description: "Use when deciding HOW to find information — choosing or composing search modalities (lexical, structural, code-intelligence, structured-data, history, semantic/RAG, graph, durable memory) for a query and corpus."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.4.0"
allowed-tools: Read Glob Grep Bash
---

# Retrieval Strategy

Pick a modality by **what you know about the query × what you know about the corpus.**

This skill is portable across GitHub Copilot, APM, and Claude Code. Each host
installs it from the `mbeacom/context-kit` marketplace — register the marketplace
(`copilot plugin marketplace add`, `apm marketplace add`, or
`/plugin marketplace add`), then install `retrieval-core@context-kit`. It also
ships automatically with `code-search`.

## Decision flow

- Know the exact token / regex / filename? → **lexical** (`rg`, `fd`)
- Know the code *shape*, not the text? → **structural** (`ast-grep`, `semgrep`)
- Know the *symbol* (function/type) — want its definition, callers/references, or call hierarchy? → **code-intelligence** (host LSP / `global` / `ctags`)
- Querying JSON / YAML / config by schema? → **structured-data** (`jq`, `yq`, `gron`)
- Asking *when/why* something changed? → **history** (`git log -S/-G/-L`)
- Tabular data at scale (CSV/Parquet)? → **data files** (`duckdb`, `sqlite-utils`)
- Sizing / complexity of a codebase? → **metrics** (`tokei`, `scc`)
- Content inside PDFs / Office docs / archives? → **docs** (`rga`, `pandoc`)
- Only know the *meaning/intent*, or corpus is huge / unfamiliar / prose? → **semantic / RAG** (`local-rag`: `rag index` then `rag query`)
- Corpus is an Obsidian vault / link graph? → **graph** (`obsidian` bridge: graph/tags → `rag query --allowlist`). For authoring/Bases/Canvas use `kepano/obsidian-skills`.
- Asking about a prior decision, constraint, procedure, preference, or bounded
  episode across sessions? → **durable memory** (`memory`: project-scoped recall,
  then open and verify the source).
- Resuming the current task and its next action? → **handoff**, not durable memory
  (`context-handoff`: validate provenance and freshness first).

Lexical/structural/code-intelligence/structured-data/history/metrics/docs live in **code-search**.
Semantic, graph, and durable recall are available as the **local-rag**,
**obsidian**, and **memory** plugins.

## Composition (modalities are layers, not rivals)

- **Hybrid rerank:** narrow with lexical/structured-data or the obsidian graph → pipe candidate file paths to `rag query --allowlist -` (turbovec reranks only those).
- **Scope then search:** graph backlinks narrow to a subgraph → RAG within it.
- **Find then pin:** RAG surfaces candidate regions → `rg` pins exact lines.
- **Resolve then pin:** code-intelligence (LSP/`global`) returns the true symbol definition or references → `rg` pins and expands the exact lines.
- **Recall then pin:** durable memory locates a prior decision/episode → open its
  cited source and pin current repository evidence.
- **Recall then verify:** stale, conflicting, or consequential memory →
  `verify-before-trust` before it affects behavior.
- **Retrieve then expand:** begin with a compact memory/RAG result → follow only
  its bounded cue, neighbor, or source links when more context is required.
- **Verify then observe:** `verify-before-trust` first → only an
  `unable-to-check` runtime claim escalates through `runtime-evidence`'s exact-ID
  allowlisted runner → return bounded observations for a final verdict.
- **Verify then hand off:** `verify-before-trust` establishes provenance-backed
  facts → compile only the proven task state into a `context-handoff` artifact.

## Defaults

1. Start with the cheapest modality that fits (lexical is free and instant).
2. Narrow before widening; count matches (`rg -c`) before reading full output.
3. Escalate to semantic only when lexical/structural genuinely can't express the
   query (intent without known terms) or the corpus is too large/unfamiliar.
4. Treat RAG and memory results as candidate locations, not proof. Preserve source
   labels and freshness; current repository/runtime evidence wins conflicts.
5. If a needed plugin (`local-rag`, `obsidian`, `memory`) isn't installed, say so and
   suggest installing it — don't assume its tools exist.
6. Verification, runtime evidence, and handoff are separate plugins too. Recommend
   those routes when warranted, but do not fabricate unavailable agents or commands.
7. If `rtk` is installed, prefix the rtk-wrapped commands (`rg`/`git`/`find`/
   `diff`) for compact output — it passes other tools through unchanged. (See
   the `code-search` plugin's rtk reference.)
