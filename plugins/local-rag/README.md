# Local RAG

A local-first semantic search engine with an opt-in hybrid mode. `local-rag`
ships a `bin/rag` CLI that chunks and embeds a corpus through
[`ollama`](https://ollama.com) and indexes it with
[`turbovec`](https://github.com/RyanCodrai/turbovec) (a quantized vector index).
The default Ollama endpoint is localhost and needs no API key; a configured
remote `CONTEXT_KIT_OLLAMA_HOST` receives corpus chunks and queries.

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
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
bash scripts/bootstrap.sh
export PATH="$PWD/bin:$PATH"
```

Claude Code does this automatically on session start (via a `SessionStart` hook)
into `${CLAUDE_PLUGIN_DATA}/venv`.

To check readiness without installing anything:

```bash
bash scripts/bootstrap.sh --check   # exit 0 ready, 3 needs bootstrap
```

It prints `KEY=VALUE` lines: `status` (`ready`, `missing`, `stale`,
`uv-missing`), the raw `venv_status` and `uv` availability as separate fields,
the resolved `home`/`venv` paths, and the exact `bootstrap_command`. A `stale`
venv was built from different `pyproject.toml` metadata and would run outdated
code, so it is reported as clearly as a missing one. Because `uv` is only
needed to *build* the venv, an already-usable venv reports `ready` even when
`uv` is absent. Dependent tooling uses this to detect an unusable runtime on
hosts that do not deploy plugin hooks, such as APM. (Claude Code and GitHub
Copilot CLI both run this plugin's `SessionStart` bootstrap.)

## Usage

Index a corpus, then query it:

```bash
rag index <path> --name X
rag query "your question" --name X
rag query "exact terms and intent" --name X --hybrid
rag status --name X
rag list
rag remove --name X --yes
```

Each named index is persisted under
`${CONTEXT_KIT_DATA}/indexes/<name>/` (or `${CLAUDE_PLUGIN_DATA}` inside
Claude Code), so queries are fast and survive across sessions.

### Index lifecycle

Index names remain backward-compatible with earlier releases: any non-empty
single path component except `.` or `..` is accepted, including names with
spaces or more than 80 characters. Path separators (`/` and `\`) and NUL are
rejected. These containment rules apply consistently to `index`, `query`,
`status`, and `remove`.

`rag remove --name X --yes` permanently removes one named index. The command is
non-interactive and refuses to run without `--yes`; missing indexes fail clearly.
Indexing, querying, status inspection, and removal share a per-index process
lock, so removal fails clearly while that index is in use. Once locked, removal
moves only the selected index out of the active namespace, then unlinks its flat
artifact files without recursive directory deletion. Other indexes are
untouched, and incomplete cleanup is reported with the quarantined artifact
location rather than silently ignored.

Portable environment variables:

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_LOCAL_RAG_HOME` | venv location only, when it must differ from index storage | — (defaults to `CONTEXT_KIT_DATA`) |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |

`CONTEXT_KIT_DATA` normally holds both the venv and the indexes. Set
`CONTEXT_KIT_LOCAL_RAG_HOME` only when a caller needs to redirect *index data*
to an isolated store while still using one shared bootstrapped venv — the
`memory` plugin does this to keep each project's index inside its own
project-isolated provider directory. When it is unset, behavior is unchanged.

The pre-rename `PRODUCTIVITY_SKILLS_*` names still resolve as a deprecated alias
(`CONTEXT_KIT_*` → `PRODUCTIVITY_SKILLS_*` → Claude fallback).

## Hybrid retrieval

Semantic-only retrieval remains the default. `--hybrid` adds SQLite FTS5 lexical
BM25 candidates and fuses them with turbovec semantic candidates using deterministic
reciprocal-rank fusion: `1.0 / (60 + semantic_rank) + 1.0 / (60 + lexical_rank)`.
Each source retrieves `3 × k` candidates before fusion, so the candidate depth is
greater than the requested final result count. JSON results include source offsets
and per-source rank/score metadata; text output remains compact.

`rag query` also accepts an `--allowlist` of candidate documents (read from a file,
or `-` for stdin), which applies to both semantic and lexical candidates. For
example, feeding Obsidian backlinks into a hybrid query:

```bash
obsidian backlinks file="X" | rag query "..." --hybrid --allowlist -
```

FTS5 is detected and backfilled automatically for existing indexes. `rag status`
reports its `fts5` capability. If the SQLite build lacks FTS5, semantic retrieval
continues to work but `--hybrid` exits with a clear error.

MIT © Mark Beacom.
