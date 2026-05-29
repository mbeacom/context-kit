# Retrieval Core

The spine of the `productivity-skills` marketplace. Provides:

- **`retrieval-strategist`** (agent) — picks and sequences retrieval modalities,
  including hybrid composition (lexical/structured narrows → vectors rerank).
- **`retrieval-strategy`** (skill) — the decision-flow reference both the agent
  and humans use.

Install standalone in Claude Code, or get it automatically by installing
`code-search`. For GitHub Copilot, copy
`skills/retrieval-strategy/` into `.github/skills/retrieval-strategy/` or
`~/.copilot/skills/retrieval-strategy/`. The `retrieval-strategist` agent can be
adapted to `.github/agents/retrieval-strategist.agent.md` by using Copilot-style
frontmatter (`tools: [read, search, execute]`).

MIT © Mark Beacom.
