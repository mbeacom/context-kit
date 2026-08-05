# memory

Durable, provenance-bound memory for project decisions, constraints, procedures,
facts, and bounded episodes. The plugin adds a portable memory contract,
capture/recall/review commands, a standard-library provider adapter, and
opt-in Claude lifecycle hooks.

The bundled `rag` provider gives offline semantic recall using `local-rag`,
which is a hard dependency. MemPalace remains optional and is installed
separately. `local-rag` is also the general corpus RAG engine;
`context-handoff` remains the authoritative current-task artifact.

## Install

```bash
# GitHub Copilot
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install memory@context-kit

# APM
apm marketplace add mbeacom/context-kit
apm install memory@context-kit

# Claude Code
/plugin marketplace add mbeacom/context-kit
/plugin install memory@context-kit
```

Installing `memory` also installs `context-handoff`, `verify`, and
`retrieval-core`.

## Local-only reviewed records

Python 3 is the only requirement. Configure an explicit project and plugin root:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" validate record.md
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  capture record.md --provider none
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy" --provider none
```

Records default to `~/.local/share/context-kit/memory`; override with
`CONTEXT_KIT_MEMORY_HOME`. Local recall searches reviewed primary memories and
cue anchors without requiring an external provider. Active recall uses only
effective `accepted/current` records. Captured record files never change:
`record-state <id> --reason ...` appends reviewed state transitions instead.
Use `search --include-inactive` for a local audit of inactive history.

## Semantic recall with the bundled `rag` provider

Local recall is lexical. For meaning-based recall, use the first-party `rag`
provider — this repository's `local-rag` plugin, installed automatically as a
dependency, so **no external tool is required**:

```bash
bash plugins/local-rag/scripts/bootstrap.sh   # Claude runs this on SessionStart
ollama pull nomic-embed-text
export CONTEXT_KIT_MEMORY_PROVIDER=rag

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor --bootstrap
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" sync-provider --apply
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy"
```

`doctor` verifies the local-rag runtime before probing the CLI and refuses with
the exact bootstrap command when the venv is missing or stale; `--bootstrap`
builds it in place. This matters on GitHub Copilot and APM, which do not run
Claude's `SessionStart` hook.

Records stay the system of record: the index is a rebuildable projection of
accepted/current records, and hits are bound back to those records before being
returned. If the provider is unreachable, `search` falls back to lexical local
search and labels the result `degraded_from` rather than passing lexical hits
off as semantic recall. A stale index refuses instead of degrading.

See [`references/provider-rag.md`](skills/memory-workflows/references/provider-rag.md).

## Optional MemPalace provider

```bash
uv tool install mempalace
export CONTEXT_KIT_MEMORY_PROVIDER=mempalace

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy"
```

Each configured project gets an isolated MemPalace palace. The adapter uses
exact argv with no shell, preserves records locally, and never installs or
imports MemPalace itself. Only `sync-provider --apply` writes or rebuilds the
provider store. Eligible capture records a pending-sync receipt; run an
explicit sync after eligible captures or state changes before provider-backed
recall. Reconciliation preserves the immediately previous store before replacement and
removes older generated backups after the success receipt is durable.

## Mine past Copilot sessions

`propose-from-session` extracts the human-visible conversation from GitHub
Copilot CLI logs into reviewable candidates. It proposes; it never captures:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  propose-from-session ~/.copilot/session-state           # dry run, writes nothing
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  propose-from-session ~/.copilot/session-state --write
```

Only top-level human and assistant turns are retained. Subagent task prompts,
generated skill/agent/command context, tool-nested messages, and model reasoning
are excluded by construction — across a real 115-session corpus only 24 of 729
`user.message` events were actually human-authored. Detected credentials block
the write unless `--redact` is passed. A transcript is not an atomic memory, so
authoring a `memory-v1` record from a candidate stays an explicit judgment step.

See [`references/session-mining.md`](skills/memory-workflows/references/session-mining.md).

## Opt-in lifecycle queue

Claude hooks are inert until enabled:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

Enabled hooks queue exact payloads locally for explicit review; they never create
memory records or mutate MemPalace. GitHub Copilot and APM do not run Claude
hooks.

## Components

| Component | Purpose |
| --- | --- |
| `memory-workflows` skill | Capture, recall, freshness, cue, and consolidation policy. |
| `/capture-memory` | Build and validate one reviewed durable record. |
| `/recall-memory` | Search memory, then pin current evidence. |
| `/review-memory` | Review freshness, conflicts, and consolidation proposals. |
| `/archive-handoff` | Explicitly preserve a validated handoff as historical memory. |
| `memory-provider.py` | Stdlib validator, local store, MemPalace adapter, and hook dispatcher. |

## Safety boundaries

- New records start proposed and retain immutable evidence.
- Recall results are leads, not proof.
- Consolidation creates supersession history; it does not erase evidence.
- Lifecycle payload queuing is disabled by default.
- Project data never falls back to a global provider store.
- MemPalace and Memora informed the design; this implementation is independent.

## Supported providers

Three provider modes are supported: `none` (lexical, no dependencies), `rag`
(first-party offline semantic recall via the bundled `local-rag` dependency),
and `mempalace` (optional, installed separately). Memora informed the memory
contract design but is not a runtime provider today.
See [`skills/memory-workflows/references/provider-qualification.md`](skills/memory-workflows/references/provider-qualification.md)
for the full qualification policy and the current decision table with revisit
triggers for Memora.
