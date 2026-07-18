# local-rag

!!! abstract "Fully-local semantic search"
    A `bin/rag` CLI that chunks and embeds a corpus with **ollama** and indexes it
    with **turbovec** (a quantized vector index). No cloud calls, no API keys —
    everything runs on your machine.

`local-rag` is notes-first but corpus-agnostic: loaders are pluggable, so the same
engine can index Markdown notes, code, or any text corpus. Named indexes persist
across sessions for fast repeat queries.

## Install

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install local-rag@context-kit
    ```

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

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — bootstraps the plugin's Python venv.
- [`ollama`](https://ollama.com) running locally with an embedding model:

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
rag status --name notes               # counts, model, dim
```

Each named index is persisted under `${CONTEXT_KIT_DATA}/indexes/<name>/` (or
`${CLAUDE_PLUGIN_DATA}` inside Claude Code), so queries are fast and survive across
sessions.

## Hybrid retrieval

`rag query` accepts an `--allowlist` of candidate documents (from a file, or `-`
for stdin), combining lexical/graph signals with semantic ranking:

```bash
# Feed Obsidian backlinks into a semantic query
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -
```

This is the bridge the [obsidian](obsidian.md) plugin drives.

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
| **Engine** | ollama (embeddings) + turbovec (index) |
| **Dependencies** | `uv`, `ollama` + an embedding model |
| **License** | MIT |
