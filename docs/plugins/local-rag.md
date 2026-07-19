# local-rag

!!! abstract "Local-first semantic and hybrid search"
    A `bin/rag` CLI that chunks and embeds a corpus with **ollama** and indexes it
    with **turbovec** (a quantized vector index). Optional `--hybrid` retrieval
    fuses vectors with SQLite FTS5/BM25. The default Ollama endpoint is localhost
    and needs no API key; a configured remote endpoint receives submitted text.

`local-rag` is notes-first but corpus-agnostic: loaders are pluggable, so the same
engine can index Markdown notes, code, or any text corpus. Named indexes persist
across sessions for fast repeat queries.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install local-rag@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install local-rag@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install local-rag@context-kit
    ```

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — bootstraps the plugin's Python venv.
- [`ollama`](https://ollama.com) running locally with an embedding model:
- SQLite compiled with FTS5 for optional `--hybrid` queries. Semantic-only
  retrieval remains available when FTS5 is absent.

    ```bash
    ollama pull nomic-embed-text
    ```

Claude Code creates the venv automatically on session start (a `SessionStart`
hook) into `${CLAUDE_PLUGIN_DATA}/venv`. **GitHub Copilot and APM don't run Claude
hooks**, so bootstrap it once yourself from a clone:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit/local-rag"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
```

## Usage

```bash
rag index <path> --name notes        # build/update (incremental)
rag query "your question" --name notes --k 8
rag query "your question" --name notes --k 8 --hybrid
rag status --name notes               # counts, model, dim
rag list                              # known indexes
rag remove --name notes --yes         # permanent, non-interactive removal
```

Each named index is persisted under `${CONTEXT_KIT_DATA}/indexes/<name>/` (or
`${CLAUDE_PLUGIN_DATA}` inside Claude Code), so queries are fast and survive across
sessions.

### Index lifecycle

Index names remain backward-compatible with earlier releases: any non-empty
single path component except `.` or `..` is accepted, including names with
spaces or more than 80 characters. Path separators (`/` and `\`) and NUL are
rejected. The same containment validation protects `index`, `query`, `status`,
and `remove`.

`rag remove --name NAME --yes` permanently removes exactly one named index and
never prompts. It refuses to run without `--yes`, fails clearly for missing
indexes, and refuses while that index is in use. Indexing, querying, status
inspection, and removal share a per-index process lock. Once locked, removal
moves the selected index out of the active namespace before non-recursively
unlinking its flat artifact files. Other indexes remain untouched; any
incomplete cleanup reports the quarantined artifact location.

## Hybrid retrieval and scoping

`--hybrid` retrieves a deeper semantic and lexical candidate set, then applies
deterministic reciprocal-rank fusion. It preserves vector similarity, BM25,
per-source ranks, fused rank/score, and source offsets in JSON output:

```bash
rag query "billing retry policy" --name notes --hybrid --json
```

This helps exact names and intent reinforce one another without pretending their
raw scores are directly comparable. If FTS5 is unavailable, `--hybrid` fails
clearly; it never silently degrades to semantic-only results.

`rag query` accepts an `--allowlist` of candidate documents (from a file, or `-`
for stdin). The allowlist scopes both semantic and lexical candidates:

```bash
# Feed Obsidian backlinks into a semantic query
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -
```

This is the bridge the [obsidian](obsidian.md) plugin drives. After either query
mode surfaces a candidate, use the returned offsets plus `rg` or Read to pin the
exact evidence.

## Configuration

Set via Claude `userConfig` or the portable environment variables:

| Variable | Purpose | Default | Claude fallback |
| --- | --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage | — | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `nomic-embed-text` | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `http://localhost:11434` | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |

The pre-rename `PRODUCTIVITY_SKILLS_*` names still resolve as a deprecated alias
(`CONTEXT_KIT_*` → `PRODUCTIVITY_SKILLS_*` → Claude fallback).

## At a glance

| | |
| --- | --- |
| **Category** | retrieval |
| **Provides** | `bin/rag` CLI, a skill, a bootstrap hook |
| **Engine** | ollama embeddings + turbovec vectors + optional SQLite FTS5/BM25 RRF |
| **Dependencies** | `uv`, `ollama` + an embedding model; SQLite FTS5 for `--hybrid` |
| **License** | MIT |
