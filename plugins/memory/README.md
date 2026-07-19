# memory

Durable, provenance-bound memory for project decisions, constraints, procedures,
facts, and bounded episodes. The plugin adds a portable memory contract,
capture/recall/review commands, a standard-library provider adapter, and
opt-in Claude lifecycle hooks.

MemPalace is optional and installed separately. `local-rag` remains the corpus
RAG engine; `context-handoff` remains the authoritative current-task artifact.

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
cue anchors without requiring an external provider.

## Optional MemPalace provider

```bash
uv tool install mempalace
export CONTEXT_KIT_MEMORY_PROVIDER=mempalace

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy"
```

Each configured project gets an isolated MemPalace palace. The adapter uses
exact argv with no shell, preserves records locally before archival, and never
installs or imports MemPalace itself.

## Opt-in automatic capture

Claude hooks are inert until enabled:

```bash
export CONTEXT_KIT_MEMORY_PROVIDER=mempalace
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

GitHub Copilot and APM do not run Claude hooks. Use explicit commands or
configure the host's native MemPalace integration separately.

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
- Automatic capture is disabled by default.
- Project data never falls back to a global provider store.
- MemPalace and Memora informed the design; this implementation is independent.
