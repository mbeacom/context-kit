# indexkit

Offline hybrid retrieval: build a local semantic + lexical index over your files
and query it. Chunks and embeds a corpus through [`ollama`](https://ollama.com),
indexes it with [`turbovec`](https://github.com/RyanCodrai/turbovec) (a quantized
vector index), and fuses that with SQLite FTS5/BM25 for opt-in hybrid search.

No API key and no network egress by default — the embedding endpoint is
localhost. A configured remote `CONTEXT_KIT_OLLAMA_HOST` receives corpus chunks
and queries, so that is the one setting that sends data off the machine.

Notes-first but corpus-agnostic: loaders are pluggable, so the same engine can
index Markdown notes, code, or any text corpus.

> Formerly `local-rag`. The old name claimed a deployment property that a
> supported setting falsifies, and understated an engine that also does lexical
> retrieval. Pre-rename environment variables are still honored.

## Install

```bash
pip install indexkit          # or: uv tool install indexkit
ollama pull nomic-embed-text  # once
```

That is the whole setup — no plugin host, no bootstrap step. Indexes default to
`${XDG_DATA_HOME:-~/.local/share}/indexkit`.

```bash
indexkit index ~/notes --name notes
indexkit query "how did we handle retry backoff" --name notes --k 8
```

To work from a clone instead — for contributing, or to run an unreleased
revision:

```bash
# From a clone of https://github.com/mbeacom/context-kit
pip install ./plugins/indexkit    # or: uv tool install ./plugins/indexkit
```

### As a context-kit plugin

Claude Code and GitHub Copilot CLI auto-bootstrap the bundled `bin/indexkit`
launcher from the plugin's `SessionStart` hook, into `${CLAUDE_PLUGIN_DATA}/venv`
— for Copilot, `~/.copilot/plugin-data/<marketplace>/indexkit/venv`. In that
mode the host controls where indexes live.

The launcher prefers that bootstrapped venv, then falls back to an `indexkit`
already on your `PATH`, then to any importable `indexkit` module. So a
pip-installed copy satisfies the plugin too, and a missing venv is not fatal.

## Requirements

- [`ollama`](https://ollama.com) running with an embedding model pulled:

  ```bash
  ollama pull nomic-embed-text
  ```

- [`uv`](https://docs.astral.sh/uv/) — **only** for the plugin bootstrap path.
  A `pip install` needs nothing beyond Python 3.10+.

For APM or manual plugin usage — or on any host where the venv is missing or
stale — bootstrap it yourself into a neutral data location:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
bash scripts/bootstrap.sh
export PATH="$PWD/bin:$PATH"
```

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
indexkit index <path> --name X
indexkit query "your question" --name X
indexkit query "exact terms and intent" --name X --hybrid
indexkit status --name X
indexkit list
indexkit remove --name X --yes
```

Each named index is persisted under `<data-dir>/indexes/<name>/`, so queries are
fast and survive across sessions. The data directory resolves in this order:

1. `CONTEXT_KIT_DATA` (or the `PRODUCTIVITY_SKILLS_DATA` alias)
2. `CLAUDE_PLUGIN_DATA`, set by a plugin host
3. `${XDG_DATA_HOME:-~/.local/share}/indexkit` — the standalone default

An existing `~/.claude/plugins/data/indexkit` directory still wins over the
standalone default while that default has not been created, so upgrading a
plugin install does not orphan indexes you already built.

### Index lifecycle

Index names remain backward-compatible with earlier releases: any non-empty
single path component except `.` or `..` is accepted, including names with
spaces or more than 80 characters. Path separators (`/` and `\`) and NUL are
rejected. These containment rules apply consistently to `index`, `query`,
`status`, and `remove`.

`indexkit remove --name X --yes` permanently removes one named index. The command is
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
| `CONTEXT_KIT_INDEXKIT_HOME` | venv location only, when it must differ from index storage | — (defaults to `CONTEXT_KIT_DATA`) |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |
| `XDG_DATA_HOME` | relocates the standalone default data directory | — |

None of these are required for a standalone install; all have defaults.
The pre-rename `CONTEXT_KIT_LOCAL_RAG_HOME` is still read as a fallback for
`CONTEXT_KIT_INDEXKIT_HOME`.

`CONTEXT_KIT_DATA` normally holds both the venv and the indexes. Set
`CONTEXT_KIT_INDEXKIT_HOME` only when a caller needs to redirect *index data*
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

`indexkit query` also accepts an `--allowlist` of candidate documents (read from a file,
or `-` for stdin), which applies to both semantic and lexical candidates. For
example, feeding Obsidian backlinks into a hybrid query:

```bash
obsidian backlinks file="X" | indexkit query "..." --hybrid --allowlist -
```

FTS5 is detected and backfilled automatically for existing indexes. `indexkit status`
reports its `fts5` capability. If the SQLite build lacks FTS5, semantic retrieval
continues to work but `--hybrid` exits with a clear error.

MIT © Mark Beacom.
