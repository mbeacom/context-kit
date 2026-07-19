# memory

`memory` adds durable, provenance-bound recall for information that should
outlive one task: prior decisions, constraints, procedures, preferences, facts,
and bounded episodes.

It is deliberately separate from:

- **`context-handoff`**, which owns authoritative current task state;
- **`local-rag`**, which owns semantic/hybrid search across document corpora;
- **repository and runtime evidence**, which determine what is true now.

Memory results are leads. The workflow always recalls, opens the original source,
checks freshness, and verifies consequential claims before acting.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install memory@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install memory@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install memory@context-kit
    ```

`memory` depends on `context-handoff`, which pulls `verify` and then
`retrieval-core`.

## Memory model

Every `context-kit/memory-v1` record has three retrieval layers:

1. immutable evidence or a precise evidence pointer;
2. one concise primary memory;
3. zero to three cue anchors for alternate phrasing.

Project records also carry repository, branch, HEAD, observation/capture times,
source hash, review state, freshness, and supersession links. New abstractions
never replace the evidence from which they were derived.

This independently implemented design combines MemPalace's useful verbatim
storage/rebuildable-index boundary with Memora-inspired primary memories, cue
anchors, rank fusion, evidence links, and reviewable consolidation.

## Local-only capture

The adapter uses only Python 3 and can preserve reviewed records without an
external provider:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  validate record.md
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  capture record.md --provider none
```

Records default to `~/.local/share/context-kit/memory`; override
`CONTEXT_KIT_MEMORY_HOME`.

## Optional MemPalace provider

[MemPalace](https://github.com/MemPalace/mempalace) is installed separately:

```bash
uv tool install mempalace

export CONTEXT_KIT_MEMORY_PROVIDER=mempalace
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_HOME="$HOME/.local/share/context-kit/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy" --results 8
```

The adapter gives each project an isolated palace below
`CONTEXT_KIT_MEMORY_HOME`, invokes exact argv without a shell, and preserves a
local exact copy before provider archival. It does not vendor MemPalace, install
dependencies, enable a writable MCP server, or use a global knowledge graph.

## Explicit workflows

| Command | Purpose |
| --- | --- |
| `/capture-memory` | Create and validate one proposed/accepted durable record. |
| `/recall-memory` | Search project memory, then open and verify the source. |
| `/review-memory` | Check freshness/conflicts and propose supersession. |
| `/archive-handoff` | Preserve one validated handoff as historical evidence. |

Consolidation is propose-only. A replacement creates a new record and
`supersedes` edge; prior evidence remains auditable.

## Opt-in automatic capture

Claude lifecycle hooks ship **disabled**. Enable only after provider setup,
project scoping, and a retention/privacy decision:

```bash
export CONTEXT_KIT_MEMORY_PROVIDER=mempalace
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

`Stop` and `PreCompact` forward in the foreground with bounded timeouts.
`SessionEnd` saves a mode-0600 pending payload and starts a detached worker so
the short host shutdown budget does not lose the final capture.

GitHub Copilot and APM do not run Claude hooks. Their default remains explicit
capture unless the user separately configures a native MemPalace integration.

## Configuration

| Variable | Purpose |
| --- | --- |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none` (default) or `mempalace`. |
| `CONTEXT_KIT_MEMORY_HOME` | Reviewed records and project-isolated provider data. |
| `CONTEXT_KIT_MEMORY_PROJECT` | Required explicit project scope. |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | Enables Claude lifecycle forwarding when truthy. |
| `CONTEXT_KIT_MEMORY_ROOT` | Installed plugin root for portable command use. |
| `CONTEXT_KIT_MEMPALACE_BIN` | Optional absolute MemPalace executable override. |

## Safety defaults

- no automatic capture unless explicitly enabled;
- no global project-memory fallback;
- no destructive consolidation;
- no transcript harvesting by the context-kit adapter;
- no claim of current truth without source/freshness checks;
- no duplicate repository corpus indexing by default.
