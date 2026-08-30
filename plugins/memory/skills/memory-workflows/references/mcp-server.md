# MCP Server

`memory` ships an optional stdio MCP server so hosts that consume **skills plus
MCP** — GitHub Copilot, Claude Code, Scout-style agents, and package-only hosts
— can use durable memory.

## Why MCP is warranted here

The context-budget rule is *reach for MCP last*: a connected server advertises
its tool schemas into the model's context on **every turn**, so it has a
standing cost even when unused. Memory clears that bar because it is **live
local state** (a store that changes across sessions) plus **actions** (propose,
recall) — not static knowledge a skill could carry. That is the documented
legitimate case, and it is why the surface is three tools rather than a wrapper
around the whole CLI.

## Register

GitHub Copilot and Claude Code plugin installs read the bundled definition
automatically:

```json
{
  "mcpServers": {
    "context-kit-memory": {
      "type": "stdio",
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"],
      "env": {
        "CONTEXT_KIT_MEMORY_HOME": "${CONTEXT_KIT_MEMORY_HOME}",
        "CONTEXT_KIT_MEMORY_PROJECT": "${CONTEXT_KIT_MEMORY_PROJECT}"
      }
    }
  }
}
```

Copilot does not populate Claude's `userConfig` fields for a
plugin-contributed MCP server. The bundled definition therefore forwards the
portable project and home variables. Explicit project configuration is still
preferred and always wins.

GitHub Copilot Desktop can also use the plugin's trusted ephemeral session
binding. `SessionStart` accepts only host-authored `cwd` and `sessionId`, requires
an exact match with the MCP child's `COPILOT_AGENT_SESSION_ID`, and binds the
normalized project only for a canonical `github.com/owner/repository` origin on
POSIX. Other Git hosts, deeper namespaces, and Windows require explicit project
configuration. This avoids the unsafe MCP working directory/PWD guess without
adding project scope to any tool schema.

Package-only and other hosts configure MCP their own way; point them at the same
command with an absolute path:

```bash
python3 /path/to/context-kit/plugins/memory/mcp/server.py
```

Environment:

| Variable | Purpose |
| --- | --- |
| `CONTEXT_KIT_MEMORY_PROJECT` | Explicit `owner/repository` scope; required outside supported Copilot plugin sessions. |
| `CONTEXT_KIT_MEMORY_HOME` | Record store root. |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none`, `rag`, or `mempalace` for recall. |

There is no default or global project. Resolution order is explicit
`--project`, `CONTEXT_KIT_MEMORY_PROJECT`, deprecated
`PRODUCTIVITY_SKILLS_MEMORY_PROJECT`, `CLAUDE_PLUGIN_OPTION_PROJECT`, then a
matching trusted Copilot session binding. With none present every tool refuses.
Project scope never comes from MCP cwd, `PWD`, prompt content, or a
model-supplied tool argument.

## Tools

| Tool | Wraps | Notes |
| --- | --- | --- |
| `memory_recall` | `search` | Active-only. Returns candidate leads with provenance. |
| `memory_capture` | `capture` | Persists a `memory-v1` record as **proposed**. |
| `memory_review` | `review` | Read-only listing with effective state. |

Deliberately **not** exposed: `sync-provider`, `record-state` promotion, backup
pruning, session mining, and anything destructive. Those stay explicit CLI
operations a person runs.

MCP capture requires an absolute `source` path. Plugin hosts may launch the
server with the plugin directory as its working directory, so a
repository-relative evidence path cannot be resolved safely at this boundary.
It reads that exact path with the host user's authority. Keep the server limited
to trusted sessions and retain host approval for `memory_capture`; the tool is
annotated as a non-read-only, non-destructive, idempotent operation.

## The surface cannot activate memory

`capture` derives a record's initial state from its frontmatter, so an agent
that could write `review: accepted` would be able to activate a memory with no
human review — the review gate would be theater.

The server therefore **refuses any record whose frontmatter `review` is not
`proposed`**. A proposal is inert: it does not appear in active recall and is
not indexed by a provider. Promotion happens only through the append-only CLI:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  record-state <id> --review accepted --reason "Checked the cited evidence."
```

Fabricated provenance is caught independently: `capture` validates the record,
and `source_hash` is verified against the actual source bytes.

## Design

The server is a **surface, not a source of truth**. Every tool shells out
to `memory-provider.py` with exact argv and no shell, so contract validation,
project resolution/isolation, review state, and reconciliation have exactly one
implementation and the CLI and MCP paths cannot drift. `mcp.py` contains no
session-binding logic.

It is standard library only, adds no runtime dependency, needs no daemon, and
does not depend on Claude hooks.

Failures are returned as tool results with `isError: true` rather than JSON-RPC
errors, so the model can read the refusal and correct itself. Protocol-level
faults (unknown method, unknown tool, malformed frame) remain JSON-RPC errors.
Malformed input never ends the session.
