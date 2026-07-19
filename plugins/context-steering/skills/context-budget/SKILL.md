---
name: context-budget
description: "Use when deciding WHERE a piece of guidance should live — always-on memory (CLAUDE.md / AGENTS.md), a path-scoped rule, an on-demand skill, a delegated subagent, a connected MCP server, or a deterministic hook — and how to keep the always-on context budget small."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read
---

# Context Budget

Everything that is **always on** costs tokens on every turn: project memory, every installed skill's name and description, and every connected MCP server's tool schemas. Steer agents by placing each piece of guidance at the cheapest layer that still fires when needed.

## Decision matrix

| Layer | Loads when | Best for | Cost |
| --- | --- | --- | --- |
| **Always-on memory** (`CLAUDE.md` / `AGENTS.md`) | Every turn | A few durable, always-relevant rules | High (persistent) |
| **Path-scoped rule** | When files matching a glob are touched | Conventions specific to an area, such as `backend/**` | Medium |
| **Skill (`SKILL.md`)** | On demand when its description matches | Large how-to knowledge you do not always need | Low always-on (just name and description); full body only when triggered |
| **Subagent** | When delegated | Isolatable, parallel, or large-context work you want off the main thread | Low (separate context window) |
| **MCP server** | Its tools are offered every turn (schemas always-on); the call runs on demand | A live external system or action the repo and local CLIs can't provide — issues, a database, a browser, a SaaS API | Medium–high always-on (tool schemas) + network/auth |
| **Hook** | Deterministically on an event (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SessionStart`) | Enforcement that must not depend on the model remembering | Near-zero tokens; runs as code |

## How to choose

1. Is it enforcement that must always happen? Use a **hook**.
2. Is it always relevant and short? Put it in **memory**.
3. Is it specific to a path, package, or area? Use a **path-scoped rule**.
4. Is it large know-how needed only sometimes? Make it a **skill** with references.
5. Does it need isolation, parallelism, or a large scratch context? Delegate to a **subagent**.
6. Does it need a *live* external system or action — not local, not static? Connect an **MCP server**, but only the ones you use (their tool schemas tax every turn).

## Keep the budget small

- Move detail out of `CLAUDE.md` / `AGENTS.md` into skills and `references/` files so the full text loads only on demand.
- Prefer one well-scoped skill with progressive-disclosure references over many tiny skills whose descriptions all stay always-on.
- Delete stale memory instead of layering exceptions on top of it.
- Put deterministic checks in hooks, not prose the model has to remember.
- Connect only the MCP servers a task actually uses — each server's tool schemas sit in context every turn, like skill descriptions.
- Keep path-scoped rules crisp: local conventions, not full design docs.

## More detail

- [`references/decision-matrix.md`](references/decision-matrix.md) explains the layers, tradeoffs, and anti-patterns.
- [`references/mcp-as-context.md`](references/mcp-as-context.md) covers when to reach for an MCP server vs a skill, CLI, or subagent, and the always-on cost of its tool schemas.
- [`references/examples.md`](references/examples.md) gives worked placement examples.
- [`../../examples/`](../../examples/) contains inert rule and hook templates to copy into your own repository.

## Portability

The placement model works across GitHub Copilot / `AGENTS.md`-style hosts and Claude Code. Hook and rule mechanisms differ by host; `examples/` uses Claude Code JSON as the concrete case while keeping the guidance host-neutral. Install with `copilot plugin install context-steering@context-kit`, `apm install context-steering@context-kit`, or `/plugin install context-steering@context-kit`.
