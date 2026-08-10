# memory

Durable, provenance-bound memory for project decisions, constraints, procedures,
facts, and bounded episodes. The plugin adds a portable memory contract,
capture/recall/review commands, a standard-library provider adapter, and
opt-in Claude lifecycle hooks.

The bundled `rag` provider gives offline semantic recall using `indexkit`,
which is a hard dependency. MemPalace remains optional and is installed
separately. `indexkit` is also the general corpus RAG engine;
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

### Without a plugin host: the `memorykit` package

The contract, validator, and MCP server are also packaged as **`memorykit`**, a
pure-standard-library Python package (ADR-0002, ADR-0009).

```bash
pip install memorykit             # or: uv tool install memorykit
```

To work from a clone instead — for contributing, or to run an unreleased
revision:

```bash
# From a clone of https://github.com/mbeacom/context-kit
pip install ./plugins/memory      # or: uv tool install ./plugins/memory
```

Either way that is the whole install: no bootstrap step, no plugin runtime, no
Claude-specific paths.

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository

memorykit validate record.md
memorykit capture record.md
memorykit search "why did we change retry policy"
memorykit-mcp                  # stdio MCP server, for an MCP client to spawn
```

**Requirements: Python 3.10+ and `git` on `PATH`.** The package has no Python
package dependencies — `pip install` pulls in nothing else, and the test suite
enforces that, because being importable with an empty `site-packages` is what
makes this separable from the plugin at all. It is not, however, free of *system*
dependencies: `validate` and `capture` shell out to `git check-ref-format` to
check the `branch` field, so both refuse on a machine with no `git`. That is
deliberate. Reimplementing Git's refname rules in Python would be a fresh,
unreviewed reimplementation of a validation the contract depends on, and skipping
the check when `git` is missing would silently weaken provenance exactly where a
mistake benefits from it. Records describe a Git checkout — they carry
`repository`, `branch`, and `head` — so requiring Git to validate one is close to
tautological.

What the package does **not** include is the plugin — the `memory-workflows`
skill, the `/capture-memory`, `/recall-memory`, `/review-memory`, and
`/archive-handoff` commands, and the lifecycle hooks are agent-host content, not
a Python package, and remain plugin-only. The package is the engine; the plugin
is the engine plus the workflow that drives it.

The plugin bundles this same code and prefers its **bundled** copy over any
installed `memorykit`, so plugin version X always runs provider version X. That
is the reverse of the `indexkit` launcher's preference, and deliberate.

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
provider — this repository's `indexkit` plugin, installed automatically as a
dependency, so **no external memory provider is required**. It still needs a
running Ollama for embeddings, plus a usable `indexkit` runtime:

```bash
pip install indexkit                         # or: bash plugins/indexkit/scripts/bootstrap.sh
ollama pull nomic-embed-text
export CONTEXT_KIT_MEMORY_PROVIDER=rag

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" sync-provider --apply
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  search "why did we change retry policy"
```

`doctor` resolves the `indexkit` executable and reports `ready` for either a
packaged install or the plugin's bootstrapped venv. When neither is usable it
refuses with the exact bootstrap command; `doctor --bootstrap` builds the venv
in place, which needs `uv`. Claude Code and GitHub Copilot CLI both run the
`indexkit` `SessionStart` hook, so this matters most on APM, which does not
deploy hooks, and after an upgrade leaves a stale venv.

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

## MCP surface for non-plugin hosts

An optional stdio MCP server exposes `memory_recall`, `memory_capture`, and
`memory_review` so hosts that consume skills plus MCP can use durable memory
without a plugin runtime. It is standard library only and shells out to the
same provider, so the CLI and MCP paths cannot drift.

```bash
# From the plugin:
CONTEXT_KIT_MEMORY_PROJECT=owner/repository \
  python3 "$CONTEXT_KIT_MEMORY_ROOT/mcp/server.py"

# From the package, with no plugin at all:
CONTEXT_KIT_MEMORY_PROJECT=owner/repository memorykit-mcp
```

The surface can propose memory but **cannot activate it**: a record whose
frontmatter is not `review: proposed` is refused, and proposals stay out of
active recall until promoted with the append-only `record-state` CLI.
`sync-provider`, promotion, mining, and destructive operations are not exposed.

See [`references/mcp-server.md`](skills/memory-workflows/references/mcp-server.md).

## Opt-in lifecycle queue

Claude hooks are inert until enabled:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

Enabled hooks queue exact payloads locally for explicit review; they never create
memory records or mutate a provider store. Claude Code and GitHub Copilot CLI
both load `hooks/hooks.json`; APM does not deploy hooks, so capture stays an
explicit command there.

## Components

| Component | Purpose |
| --- | --- |
| `memory-workflows` skill | Capture, recall, freshness, cue, and consolidation policy. |
| `/capture-memory` | Build and validate one reviewed durable record. |
| `/recall-memory` | Search memory, then pin current evidence. |
| `/review-memory` | Review freshness, conflicts, and consolidation proposals. |
| `/archive-handoff` | Explicitly preserve a validated handoff as historical memory. |
| `memory-provider.py` | Launcher for the `memorykit` provider: stdlib validator, local store, MemPalace adapter, and hook dispatcher. |
| `src/memorykit/` | The packaged engine (`memorykit`, not yet on PyPI): contract, validator, provider, MCP server. |

## Safety boundaries

- New records start proposed and retain immutable evidence.
- Recall results are leads, not proof.
- Consolidation creates supersession history; it does not erase evidence.
- Lifecycle payload queuing is disabled by default.
- Project data never falls back to a global provider store.
- MemPalace and Memora informed the design; this implementation is independent.

## Supported providers

Three provider modes are supported: `none` (lexical, no dependencies), `rag`
(first-party offline semantic recall via the bundled `indexkit` dependency),
and `mempalace` (optional, installed separately). Memora informed the memory
contract design but is not a runtime provider today.
See [`skills/memory-workflows/references/provider-qualification.md`](skills/memory-workflows/references/provider-qualification.md)
for the full qualification policy and the current decision table with revisit
triggers for Memora.
