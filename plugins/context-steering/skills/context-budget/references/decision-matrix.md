# Decision Matrix

Context steering is a placement problem. Each layer trades reliability, scope, and token cost differently; use the cheapest layer that still activates at the right time.

`AGENTS.md` is the emerging cross-tool project-memory convention, and `CLAUDE.md` is Claude Code's project-memory file. Treat them as the same layer: short, durable, always-on guidance.

## Always-on memory (`CLAUDE.md` / `AGENTS.md`)

- Use for a tiny set of instructions that are true for nearly every task in the repository.
- Avoid for long tutorials, area-specific style guides, temporary project notes, or rules that only matter for a few paths.
- Anti-pattern — **memory landfill**: dumping a 500-line style guide into `CLAUDE.md`. Move the narrative into a skill and keep only the trigger sentence in memory.

## Path-scoped rule

- Use for conventions that become relevant only when files in a package, directory, language, or feature area are touched.
- Avoid when the rule is global, when the host cannot scope it reliably, or when the content is a large how-to that should be loaded on demand.
- Anti-pattern — **globalizing a local rule**: telling every turn about `src/api/**` validation rules. Keep that guidance beside the area it governs.

## Skill (`SKILL.md`)

- Use for reusable, substantial know-how that should load only when the task matches a precise description.
- Avoid for universal project rules, deterministic enforcement, or tiny fragments that would be cheaper as a short memory line.
- Anti-pattern — **one mega-skill that always matches**: a broad description like "use for coding" loads a large body too often. Split by trigger and keep references behind progressive disclosure.

## Subagent

- Use when work can be isolated, parallelized, or moved into a separate scratch context: large audits, independent research threads, broad read-only sweeps, or risky experiments.
- Avoid when the task is a simple lookup, a single continuous trace, or work that needs tight main-thread coordination.
- Anti-pattern — **delegation confetti**: spawning agents for tiny lookups. The coordination overhead costs more than reading the file yourself.

## Hook

- Use when behavior must be deterministic: blocking secret writes, running a formatter after edits, injecting session context, or gating completion checks.
- Avoid when judgment is required, when the action is host-specific and not available in the target environment, or when a human should approve the action.
- Anti-pattern — **prose enforcement**: encoding a formatting rule as a paragraph and hoping the model remembers. Make it a `PostToolUse` hook so it runs every time.

## MCP server

- Use for a live external system or action the repo and local CLIs cannot provide on their own: querying a ticketing system or database, driving a browser, or calling a SaaS API, with auth and fresh state each turn.
- Avoid when the knowledge is static how-to (cheaper as a skill), when the data is local (a CLI or subagent can fetch it on demand with no standing cost), or when you would connect a server you rarely call.
- Anti-pattern — **server sprawl**: connecting a dozen MCP servers whose tool schemas sit in context every turn while you use two. Every connected server taxes the always-on budget like an always-matching skill. See [`mcp-as-context.md`](mcp-as-context.md).

## Combining layers

Good steering stacks layers without duplicating them. A short memory line can say "API conventions are path-scoped under `src/api/**`"; the scoped rule carries the conventions; a skill explains how to design a new API surface; a hook enforces formatting or secret checks; an MCP server adds a live external source only when the local layers genuinely cannot answer. Each layer owns its trigger, and you reach for MCP last.
