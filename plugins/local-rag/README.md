# Local RAG

A fully-local semantic search engine. `local-rag` ships a `bin/rag` CLI that
chunks and embeds a corpus with [`ollama`](https://ollama.com) and indexes it
with [`turbovec`](https://github.com/RyanCodrai/turbovec) (a quantized vector
index). Everything runs on your machine — no cloud calls, no API keys.

It is notes-first but corpus-agnostic: loaders are pluggable, so the same engine
can index Markdown notes, code, or any text corpus.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — used to bootstrap the plugin's Python venv.
- [`ollama`](https://ollama.com) running locally with the embedding model pulled:

  ```bash
  ollama pull nomic-embed-text
  ```

The venv is created automatically on session start (via a `SessionStart` hook)
into `${CLAUDE_PLUGIN_DATA}/venv`. You can also run it by hand:

```bash
bash scripts/bootstrap.sh
```

## Usage

Index a corpus, then query it:

```bash
rag index <path> --name X
rag query "your question" --name X
```

Each named index is persisted under `${CLAUDE_PLUGIN_DATA}/indexes/<name>/`, so
queries are fast and survive across sessions.

## Hybrid retrieval

`rag query` accepts an `--allowlist` of candidate documents (read from a file,
or `-` for stdin), letting you combine lexical/graph signals with semantic
ranking. For example, feeding Obsidian backlinks into a semantic query:

```bash
obsidian backlinks file="X" | rag query "..." --allowlist -
```

MIT © Mark Beacom.
