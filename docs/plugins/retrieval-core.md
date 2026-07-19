# retrieval-core

!!! abstract "The spine"
    A `retrieval-strategist` agent and a `retrieval-strategy` decision-flow skill
    that pick and compose search modalities (lexical, structural,
    code-intelligence, structured data, history, data files, metrics, docs,
    semantic/RAG, graph, durable memory). Every
    other retrieval plugin builds on it.

`retrieval-core` is the routing layer of the marketplace. Given a question and a
corpus, it chooses the cheapest modality that answers it — and sequences several
together when one isn't enough.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install retrieval-core@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install retrieval-core@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install retrieval-core@context-kit
    ```

You usually get it for free: installing [`code-search`](code-search.md) or
[`verify`](verify.md) pulls `retrieval-core` in directly. Installing
[`runtime-evidence`](runtime-evidence.md) or
[`context-handoff`](context-handoff.md) pulls `verify`, which transitively pulls
the spine. [`memory`](memory.md) pulls the same chain through `context-handoff`.

## Components

| Component | What it is |
| --- | --- |
| **`retrieval-strategist`** agent | Picks and sequences retrieval modalities, including hybrid composition (lexical/structured narrows → vectors rerank). |
| **`retrieval-strategy`** skill | The decision-flow reference both the agent and humans use to choose a modality. |

## Choosing a modality

The decision flow keys off **what you already know** about the target:

| You know… | Reach for | Plugin |
| --- | --- | --- |
| an exact token, regex, or filename | lexical (`rg`, `fd`) | [code-search](code-search.md) |
| the code *shape*, not the literal text | structural (`ast-grep`, `semgrep`) | [code-search](code-search.md) |
| a symbol and its definitions, references, or callers | code-intelligence (LSP, `global`, `ctags`) | [code-search](code-search.md) |
| a JSON/YAML schema path | structured-data (`jq`, `yq`, `gron`) | [code-search](code-search.md) |
| *when / why* something changed | history (`git log -S/-G/-L`) | [code-search](code-search.md) |
| a large tabular CSV/Parquet corpus | data files (`duckdb`, `sqlite-utils`) | [code-search](code-search.md) |
| codebase size or complexity | metrics (`tokei`, `scc`) | [code-search](code-search.md) |
| content inside PDFs, Office files, or archives | docs (`rga`, `pandoc`, `pdftotext`) | [code-search](code-search.md) |
| only the meaning / intent | semantic (RAG) | [local-rag](local-rag.md) |
| the corpus is an Obsidian vault | graph (backlinks / tags) | [obsidian](obsidian.md) |
| a prior decision, constraint, procedure, preference, or episode | durable memory | [memory](memory.md) |
| current task state and next action | validated handoff | [context-handoff](context-handoff.md) |
| a retrieved claim must be checked before use | verification | [verify](verify.md) |
| static verification cannot settle a runtime claim | controlled runtime evidence | [runtime-evidence](runtime-evidence.md) |

## Composition is the point

Modalities are layers, not rivals. The strategist sequences them:

- **Hybrid rerank** — lexical or structured-data narrows to a candidate file set
  → `rag query --allowlist -` reranks only those by meaning.
- **Scope then search** — graph backlinks or tags bound a subgraph → RAG within it.
- **Find then pin** — RAG surfaces `path > heading` regions → `rg` pins exact lines.
- **Resolve then pin** — code-intelligence resolves true symbol references → `rg`
  pins exact lines.
- **Recall then pin** — memory surfaces a prior decision/episode → open its cited
  source and pin current evidence.
- **Recall then verify** — stale, conflicting, or consequential memory →
  `verify-before-trust`.
- **Retrieve then expand** — follow only bounded cue, neighbor, or source links
  when the compact result is insufficient.
- **Verify then observe** — static verification escalates only an
  `unable-to-check` runtime claim to an approved exact command ID, then consumes
  the bounded evidence.
- **Verify then hand off** — verified repository facts become bounded resumable
  task state with provenance and freshness.

## What the contract suite enforces

`plugins/plugin-forge/quality/retrieval-scenarios.json` turns this documented
surface into a schema-v1 static contract: 14 primary routes, nine named
compositions, explicit cross-plugin/tool references, exact step sequences, and
near-miss boundaries. Plugin Forge runs it through the existing catalog-quality
gate in pre-commit and CI.

The gate proves schema integrity, complete declared coverage, and internal
reference consistency. It does **not** invoke `retrieval-strategist`, judge a
model response, or measure live routing accuracy. Stable scenario IDs and
expected selections are intentionally reusable by a future scheduled,
credentialed, rate-limited, non-blocking live-model trend job.

See [Architecture](../ARCHITECTURE.md) for the full modality model.

## At a glance

| | |
| --- | --- |
| **Category** | retrieval |
| **Provides** | 1 agent, 1 skill |
| **Dependencies** | none |
| **Depended on by** | `code-search`, `verify`; transitively `runtime-evidence`, `context-handoff`, `memory` |
| **License** | MIT |
