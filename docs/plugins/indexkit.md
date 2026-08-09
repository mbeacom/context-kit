# indexkit

!!! abstract "Local-first semantic and hybrid search"
    A `bin/indexkit` CLI that chunks and embeds a corpus with **ollama** and indexes it
    with **turbovec** (a quantized vector index). Optional `--hybrid` retrieval
    fuses vectors with SQLite FTS5/BM25. The default Ollama endpoint is localhost
    and needs no API key; a configured remote endpoint receives submitted text.

`indexkit` is notes-first but corpus-agnostic: loaders are pluggable, so the same
engine can index Markdown notes, code, or any text corpus. Named indexes persist
across sessions for fast repeat queries.

## Install

The CLI is published on PyPI and works on its own, with no plugin host:

```bash
pip install indexkit          # or: uv tool install indexkit
```

Install it as a plugin when you also want the bundled skill, so an agent knows
when to reach for semantic retrieval:

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install indexkit@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install indexkit@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install indexkit@context-kit
    ```

## Requirements

- [`ollama`](https://ollama.com) running locally with an embedding model:

    ```bash
    ollama pull nomic-embed-text
    ```

- SQLite compiled with FTS5 for optional `--hybrid` queries. Semantic-only
  retrieval remains available when FTS5 is absent.
- [`uv`](https://docs.astral.sh/uv/) — **only** for the plugin venv bootstrap.
  A `pip install` needs nothing beyond Python 3.10+.

Claude Code and GitHub Copilot CLI both create the venv automatically on session
start (the plugin's `SessionStart` hook) into `${CLAUDE_PLUGIN_DATA}/venv`.
**APM does not deploy hooks**, so on APM — or on any host where `--check`
reports a missing or stale venv — either install the package, which the plugin
launcher will find on `PATH`:

```bash
pip install indexkit
```

or bootstrap the plugin's own venv from a clone:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
bash plugins/indexkit/scripts/bootstrap.sh
export PATH="$PWD/plugins/indexkit/bin:$PATH"
```

## Usage

```bash
indexkit index <path> --name notes                     # build/update (incremental)
indexkit query "your question" --name notes --k 8
indexkit query "your question" --name notes --k 8 --hybrid
indexkit status --name notes                           # counts, model, dim
indexkit list                                          # known indexes
indexkit remove --name notes --yes                     # permanent, non-interactive removal
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

`indexkit remove --name NAME --yes` permanently removes exactly one named index and
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
indexkit query "billing retry policy" --name notes --hybrid --json
```

This helps exact names and intent reinforce one another without pretending their
raw scores are directly comparable. If FTS5 is unavailable, `--hybrid` fails
clearly; it never silently degrades to semantic-only results.

`indexkit query` accepts an `--allowlist` of candidate documents (from a file, or `-`
for stdin). The allowlist scopes both semantic and lexical candidates:

```bash
# Feed Obsidian backlinks into a semantic query
obsidian backlinks file="Project X" | indexkit query "open risks" --name notes --allowlist -
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
| **Provides** | `bin/indexkit` CLI, a skill, a bootstrap hook |
| **Engine** | ollama embeddings + turbovec vectors + optional SQLite FTS5/BM25 RRF |
| **Dependencies** | `ollama` + an embedding model; `uv` for the plugin bootstrap only; SQLite FTS5 for `--hybrid` |
| **License** | MIT |
