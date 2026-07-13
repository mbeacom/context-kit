# Retrieval Core

The spine of the `productivity-skills` marketplace. Provides:

- **`retrieval-strategist`** (agent) — picks and sequences retrieval modalities,
  including hybrid composition (lexical/structured narrows → vectors rerank).
- **`retrieval-strategy`** (skill) — the decision-flow reference both the agent
  and humans use.

Install standalone in Claude Code (`/plugin install retrieval-core@productivity-skills`),
or get it automatically by installing `code-search`. GitHub Copilot CLI installs it
the same way — `copilot plugin marketplace add mbeacom/productivity-skills` then
`copilot plugin install retrieval-core@productivity-skills` — and the
`retrieval-strategist` agent and `retrieval-strategy` skill come with it.

MIT © Mark Beacom.
