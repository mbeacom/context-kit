# memory

`memory` adds durable, provenance-bound recall for information that should
outlive one task: prior decisions, constraints, procedures, preferences, facts,
and bounded episodes.

It is deliberately separate from:

- **`context-handoff`**, which owns authoritative current task state;
- **`indexkit`**, which owns semantic/hybrid search across document corpora;
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

## Semantic recall with the first-party `rag` provider

Local recall is lexical. The bundled `rag` provider adds **offline semantic
recall** using `indexkit`, which `memory` hard-depends on, so no external
*memory provider* is needed. Embeddings still come from a locally running
Ollama, and `uv` bootstraps the venv once:

```bash
bash plugins/indexkit/scripts/bootstrap.sh   # Claude runs this on SessionStart
ollama pull nomic-embed-text

export CONTEXT_KIT_MEMORY_PROVIDER=rag
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor --bootstrap
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" sync-provider --apply
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy" --results 8
```

`doctor` checks the indexkit runtime before probing the CLI and refuses with
the exact bootstrap command when the venv is missing or stale; `--bootstrap`
builds it. Claude Code and GitHub Copilot CLI both run the `indexkit`
`SessionStart` hook; APM does not deploy hooks, and any host can end up with a
stale venv, so this is the host-neutral path to a working runtime.

The index is a rebuildable projection of accepted/current records, never the
system of record: hits are bound back to the local records, so review,
freshness, `source`, and `source_hash` come from the immutable artifacts. When
the provider is unreachable, `search` falls back to lexical local search and
labels it `degraded_from`; a stale index refuses instead of degrading.

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

The [continuity integration test](../ARCHITECTURE.md#tested-verification-to-continuity-boundary)
archives a current handoff, captures an accepted local record from that preserved
source, recalls its labels, and then proves newer repository state takes
precedence. No MemPalace process or network is involved.

## Mine past Copilot sessions

`propose-from-session` extracts the human-visible conversation from GitHub
Copilot CLI logs (`~/.copilot/session-state/<id>/events.jsonl`) into reviewable
`context-kit/memory-candidate-v1` candidates:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  propose-from-session ~/.copilot/session-state            # dry run
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  propose-from-session ~/.copilot/session-state --write
```

Attribution is the hard part. Copilot logs all activity in one stream, and a
subagent task prompt is written by the orchestrating model, not the person.
Across a real 115-session corpus, 611 of 729 `user.message` events carried
`parentAgentTaskId` and 94 carried a generated `source`, leaving **24** genuine
human turns. Extraction keeps a user turn only when it has neither; assistant
turns require neither `parentToolCallId` nor `parentAgentTaskId`. Reasoning
fields are never extracted.

Mining proposes and never captures — a transcript is not an atomic memory, so
authoring a record from a candidate is an explicit judgment step. Dry run is the
default, credential findings block the write unless `--redact` is passed, and
repository/branch/HEAD anchors are required rather than invented.

## MCP surface for non-plugin hosts

An optional stdio MCP server lets hosts that consume **skills plus MCP** —
GitHub Copilot, Scout-style agents, and other non-plugin runtimes — use durable
memory without a Claude plugin runtime:

```bash
CONTEXT_KIT_MEMORY_PROJECT=owner/repository \
  python3 "$CONTEXT_KIT_MEMORY_ROOT/mcp/server.py"
```

Three tools are exposed — `memory_recall`, `memory_capture`, `memory_review` —
because a connected server advertises its schemas into context on every turn.
Memory clears the "reach for MCP last" bar because it is live local state plus
actions, not static knowledge a skill could carry.

The server is a surface, not a source of truth: every tool shells out to
`memory-provider.py` with exact argv, so validation, isolation, and review state
have one implementation. It can propose memory but **cannot activate it** — a
record that is not `review: proposed` is refused, and proposals stay out of
active recall until promoted with the append-only `record-state` CLI.
`sync-provider`, promotion, mining, and destructive operations are not exposed.

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

APM does not deploy plugin hooks, so its default remains explicit
capture unless the user separately configures a native MemPalace integration.

## Configuration

| Variable | Purpose |
| --- | --- |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none` (default), `rag`, or `mempalace`. |
| `CONTEXT_KIT_MEMORY_HOME` | Reviewed records and project-isolated provider data. |
| `CONTEXT_KIT_MEMORY_PROJECT` | Required explicit project scope. |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | Enables Claude lifecycle forwarding when truthy. |
| `CONTEXT_KIT_MEMORY_ROOT` | Installed plugin root for portable command use. |
| `CONTEXT_KIT_MEMPALACE_BIN` | Optional absolute MemPalace executable override. |
| `CONTEXT_KIT_INDEXKIT_BIN` | Optional absolute `rag` executable override. |

## Safety defaults

- no automatic capture unless explicitly enabled;
- no global project-memory fallback;
- no destructive consolidation;
- no transcript harvesting by the context-kit adapter — session mining
  proposes reviewable candidates and never creates memory records;
- no claim of current truth without source/freshness checks;
- no duplicate repository corpus indexing by default.
