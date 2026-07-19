# Retrieval Core

The spine of the `context-kit` marketplace. Provides:

- **`retrieval-strategist`** (agent) — picks and sequences retrieval modalities,
  including durable memory and hybrid composition (lexical/structured narrows →
  vectors rerank).
- **`retrieval-strategy`** (skill) — the decision-flow reference both the agent
  and humans use.

Durable memory is for prior decisions, constraints, procedures, preferences, and
bounded episodes. Current task state still belongs in `context-handoff`, and
memory/RAG results must be pinned to current evidence before they drive work.

Get it automatically by installing `code-search` — or install it standalone.

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install retrieval-core@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install retrieval-core@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install retrieval-core@context-kit
```

The `retrieval-strategist` agent and `retrieval-strategy` skill come with it on
every host.

MIT © Mark Beacom.
