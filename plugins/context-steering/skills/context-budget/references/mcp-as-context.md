# MCP servers as a context source

An [MCP](https://modelcontextprotocol.io) server connects the agent to a live
external system — a ticketing API, a database, a browser, a SaaS service — and
exposes it as callable tools. In context-budget terms it is a **placement
option like any other**: it brings in context, and it has a standing cost.

## The cost that is easy to miss

Every *connected* MCP server advertises its tool list — names, descriptions, and
input schemas — into the model's context **on every turn**, exactly like an
always-on skill description. Connect ten servers and you pay for ten tool
catalogs each turn whether or not you call them. Treat connected servers like
always-matching skills: keep only the ones a task actually uses.

Other standing costs: an **auth/secret surface** (tokens, scopes), a **network
dependency and failure mode** (a down server is a broken turn), and **latency**
(a round trip per call).

## MCP vs skill vs CLI vs subagent

| Reach for… | When |
| --- | --- |
| **MCP server** | You need *live* external state or an *action* the repo and local CLIs can't provide — open issues, a production DB, a browser session, a third-party API — fresh each turn, with auth. |
| **Skill** | The knowledge is static how-to that ships in the repo. Cheaper, versioned, portable, no network. |
| **CLI (via Bash)** | The data is local or a command can fetch it on demand. No standing schema cost — it runs only when invoked. |
| **Subagent** | The work is isolatable/parallel/context-heavy. Off the main thread, no always-on cost. |

Rule of thumb: **reach for MCP last** — only when the answer genuinely requires a
live external system that a skill, a local CLI, or a subagent cannot deliver.
Everything else is cheaper and more portable.

## Portability

The *decision* is host-neutral; the *wiring* is not. Claude Code reads
`.mcp.json` / a plugin's `mcpServers`; GitHub Copilot and other hosts configure
MCP their own way. Keep server definitions in the plugin's host-specific config
and keep this "when to reach for MCP" reasoning in the portable skill body.

## Anti-patterns

- **Server sprawl** — a dozen connected servers whose schemas tax every turn
  while you call two. Disconnect the rest.
- **MCP for static knowledge** — wrapping a README or a lookup table behind a
  server when a skill (no network, no auth, versioned) would do.
- **MCP for local data** — standing up a server for something `rg`, `jq`, or a
  subagent can read directly from the repo.
