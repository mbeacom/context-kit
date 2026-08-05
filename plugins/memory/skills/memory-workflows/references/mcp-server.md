# MCP Server

`memory` ships an optional stdio MCP server so hosts that consume **skills plus
MCP** — GitHub Copilot, Scout-style agents, and other non-plugin hosts — can use
durable memory without a Claude plugin runtime.

## Why MCP is warranted here

The context-budget rule is *reach for MCP last*: a connected server advertises
its tool schemas into the model's context on **every turn**, so it has a
standing cost even when unused. Memory clears that bar because it is **live
local state** (a store that changes across sessions) plus **actions** (propose,
recall) — not static knowledge a skill could carry. That is the documented
legitimate case, and it is why the surface is three tools rather than a wrapper
around the whole CLI.

## Register

Claude Code reads the bundled definition automatically:

```json
{
  "mcpServers": {
    "context-kit-memory": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]
    }
  }
}
```

Other hosts configure MCP their own way; point them at the same command with an
absolute path:

```bash
python3 /path/to/context-kit/plugins/memory/mcp/server.py
```

Required environment:

| Variable | Purpose |
| --- | --- |
| `CONTEXT_KIT_MEMORY_PROJECT` | **Required.** Explicit `owner/repository` scope. |
| `CONTEXT_KIT_MEMORY_HOME` | Record store root. |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none`, `rag`, or `mempalace` for recall. |

There is no default project. With `CONTEXT_KIT_MEMORY_PROJECT` unset every tool
refuses, because memory must never be read from or written to an inferred
global store.

## Tools

| Tool | Wraps | Notes |
| --- | --- | --- |
| `memory_recall` | `search` | Active-only. Returns candidate leads with provenance. |
| `memory_capture` | `capture` | Persists a `memory-v1` record as **proposed**. |
| `memory_review` | `review` | Read-only listing with effective state. |

Deliberately **not** exposed: `sync-provider`, `record-state` promotion, backup
pruning, session mining, and anything destructive. Those stay explicit CLI
operations a person runs.

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

The server is a **surface, not a source of truth**. Every tool shells out to
`memory-provider.py` with exact argv and no shell, so contract validation,
project isolation, review state, and reconciliation have exactly one
implementation and the CLI and MCP paths cannot drift.

It is standard library only, adds no runtime dependency, needs no daemon, and
does not depend on Claude hooks.

Failures are returned as tool results with `isError: true` rather than JSON-RPC
errors, so the model can read the refusal and correct itself. Protocol-level
faults (unknown method, unknown tool, malformed frame) remain JSON-RPC errors.
Malformed input never ends the session.
