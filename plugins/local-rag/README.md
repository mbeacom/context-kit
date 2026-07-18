# Local RAG

A fully-local semantic search engine. `local-rag` ships a `bin/rag` CLI that
chunks and embeds a corpus with [`ollama`](https://ollama.com) and indexes it
with [`turbovec`](https://github.com/RyanCodrai/turbovec) (a quantized vector
index). Everything runs on your machine — no cloud calls, no API keys.

It is notes-first but corpus-agnostic: loaders are pluggable, so the same engine
can index Markdown notes, code, or any text corpus.

GitHub Copilot, APM, or manual users run the CLI by bootstrapping it directly and
setting the portable `CONTEXT_KIT_DATA` location. The Claude Code plugin
auto-bootstraps the CLI for you.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — used to bootstrap the plugin's Python venv.
- [`ollama`](https://ollama.com) running locally with the embedding model pulled:

  ```bash
  ollama pull nomic-embed-text
  ```

For GitHub Copilot, APM, or manual usage, bootstrap the venv yourself into a
neutral data location:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit/local-rag"
bash scripts/bootstrap.sh
export PATH="$PWD/bin:$PATH"
```

Claude Code does this automatically on session start (via a `SessionStart` hook)
into `${CLAUDE_PLUGIN_DATA}/venv`.

## Usage

Index a corpus, then query it:

```bash
rag index <path> --name X
rag query "your question" --name X
```

Each named index is persisted under
`${CONTEXT_KIT_DATA}/indexes/<name>/` (or `${CLAUDE_PLUGIN_DATA}` inside
Claude Code), so queries are fast and survive across sessions.

Portable environment variables:

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |

The pre-rename `PRODUCTIVITY_SKILLS_*` names still resolve as a deprecated alias
(`CONTEXT_KIT_*` → `PRODUCTIVITY_SKILLS_*` → Claude fallback).

## Hybrid retrieval

`rag query` accepts an `--allowlist` of candidate documents (read from a file,
or `-` for stdin), letting you combine lexical/graph signals with semantic
ranking. For example, feeding Obsidian backlinks into a semantic query:

```bash
obsidian backlinks file="X" | rag query "..." --allowlist -
```

MIT © Mark Beacom.
