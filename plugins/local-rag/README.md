# Local RAG

A fully-local semantic search engine. `local-rag` ships a `bin/rag` CLI that
chunks and embeds a corpus with [`ollama`](https://ollama.com) and indexes it
with [`turbovec`](https://github.com/RyanCodrai/turbovec) (a quantized vector
index). Everything runs on your machine — no cloud calls, no API keys.

It is notes-first but corpus-agnostic: loaders are pluggable, so the same engine
can index Markdown notes, code, or any text corpus.

The Claude Code plugin auto-bootstraps the CLI. GitHub Copilot or manual users
can run the same CLI by bootstrapping it directly and setting the portable
`PRODUCTIVITY_SKILLS_DATA` location.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — used to bootstrap the plugin's Python venv.
- [`ollama`](https://ollama.com) running locally with the embedding model pulled:

  ```bash
  ollama pull nomic-embed-text
  ```

The venv is created automatically on Claude Code session start (via a
`SessionStart` hook) into `${CLAUDE_PLUGIN_DATA}/venv`. For GitHub Copilot or
manual usage, prefer a neutral data location:

```bash
export PRODUCTIVITY_SKILLS_DATA="$HOME/.local/share/productivity-skills/local-rag"
bash scripts/bootstrap.sh
export PATH="$PWD/bin:$PATH"
```

## Usage

Index a corpus, then query it:

```bash
rag index <path> --name X
rag query "your question" --name X
```

Each named index is persisted under
`${PRODUCTIVITY_SKILLS_DATA}/indexes/<name>/` (or `${CLAUDE_PLUGIN_DATA}` inside
Claude Code), so queries are fast and survive across sessions.

Portable environment variables:

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `PRODUCTIVITY_SKILLS_DATA` | venv and index storage | `CLAUDE_PLUGIN_DATA` |
| `PRODUCTIVITY_SKILLS_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `PRODUCTIVITY_SKILLS_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |

## Hybrid retrieval

`rag query` accepts an `--allowlist` of candidate documents (read from a file,
or `-` for stdin), letting you combine lexical/graph signals with semantic
ranking. For example, feeding Obsidian backlinks into a semantic query:

```bash
obsidian backlinks file="X" | rag query "..." --allowlist -
```

MIT © Mark Beacom.
