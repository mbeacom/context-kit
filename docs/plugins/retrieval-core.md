# retrieval-core

!!! abstract "The spine"
    A `retrieval-strategist` agent and a `retrieval-strategy` decision-flow skill
    that pick and compose search modalities (lexical, structural,
    code-intelligence, history, semantic/RAG, graph, durable memory). Every
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
| a JSON/YAML schema path | structured-data (`jq`, `yq`, `gron`) | [code-search](code-search.md) |
| *when / why* something changed | history (`git log -S/-G/-L`) | [code-search](code-search.md) |
| only the meaning / intent | semantic (RAG) | [local-rag](local-rag.md) |
| the corpus is an Obsidian vault | graph (backlinks / tags) | [obsidian](obsidian.md) |
| a prior decision, constraint, procedure, preference, or episode | durable memory | [memory](memory.md) |
| current task state and next action | validated handoff | [context-handoff](context-handoff.md) |

## Composition is the point

Modalities are layers, not rivals. The strategist sequences them:

- **Hybrid rerank** — lexical or structured-data narrows to a candidate file set
  → `rag query --allowlist -` reranks only those by meaning.
- **Scope then search** — graph backlinks or tags bound a subgraph → RAG within it.
- **Find then pin** — RAG surfaces `path > heading` regions → `rg` pins exact lines.
- **Recall then pin** — memory surfaces a prior decision/episode → open its cited
  source and pin current evidence.
- **Recall then verify** — stale, conflicting, or consequential memory →
  `verify-before-trust`.
- **Retrieve then expand** — follow only bounded cue, neighbor, or source links
  when the compact result is insufficient.

See [Architecture](../ARCHITECTURE.md) for the full modality model.

## At a glance

| | |
| --- | --- |
| **Category** | retrieval |
| **Provides** | 1 agent, 1 skill |
| **Dependencies** | none |
| **Depended on by** | `code-search`, `verify`; transitively `runtime-evidence`, `context-handoff`, `memory` |
| **License** | MIT |
