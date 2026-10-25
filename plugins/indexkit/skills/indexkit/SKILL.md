---
name: indexkit
description: "Use for semantic search over a markdown corpus when keywords aren't enough and you know the meaning, not the exact words, or hybrid semantic plus lexical search. Index once, then query."
license: MIT
compatibility: "Requires the indexkit CLI (pip install indexkit, or auto-bootstrapped via uv in a plugin host) plus a running ollama with an embedding model pulled (default nomic-embed-text)."
metadata:
  author: Mark Beacom
  version: "0.3.2"
allowed-tools: Bash(indexkit:*) Bash(ollama:*) Bash(rg:*) Bash(rtk rg:*) Read Glob Grep
---

# indexkit

Offline hybrid retrieval: `indexkit` chunks a corpus, embeds it through the
configured Ollama endpoint (default localhost), indexes it with turbovec, and
fuses that with SQLite FTS5/BM25 for opt-in lexical search. A remote
`CONTEXT_KIT_OLLAMA_HOST` receives corpus chunks and queries.

## Prerequisites

- `ollama serve` running and the model pulled: `ollama pull nomic-embed-text`.
- Claude Code and GitHub Copilot CLI: the runtime is bootstrapped automatically
  on session start (uv venv). If it is missing or stale, run
  `bash "${CONTEXT_KIT_INDEXKIT_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/bootstrap.sh"`.
- APM/manual: `pip install indexkit` is enough. To work from a clone instead,
  set `CONTEXT_KIT_DATA` and run `plugins/indexkit/scripts/bootstrap.sh`.

## Resolve the CLI

The commands below are written as `indexkit`. The plugin does not put anything
on `PATH`, so resolve the CLI once, in this order, and use the first that exists:

1. `indexkit` itself, when `command -v indexkit` finds one (a `pip install`, or
   a manual `PATH` entry).
2. `"$CONTEXT_KIT_INDEXKIT_ROOT/scripts/indexkit"`, when that variable names the
   installed plugin directory.
3. `"${CLAUDE_PLUGIN_ROOT}/scripts/indexkit"` from inside this plugin on Claude
   Code.
4. The installed plugin's launcher, from any other plugin or host:
   `~/.claude/plugins/cache/*/indexkit/*/scripts/indexkit` (Claude Code; pick the
   highest version) or `~/.copilot/installed-plugins/*/indexkit/scripts/indexkit`
   (GitHub Copilot CLI).

```bash
"${CONTEXT_KIT_INDEXKIT_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/indexkit" status --name notes
```

The launcher prefers the bootstrapped venv, then an `indexkit` on `PATH`, then
an importable module. Other skills that pipe into `indexkit` (the obsidian
bridge, adr-bridge, retrieval-strategy) use this same resolution.

Check readiness without installing anything — useful on APM, which does not
deploy hooks, and after an upgrade leaves a stale venv:

```bash
bash "${CONTEXT_KIT_INDEXKIT_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/bootstrap.sh" --check   # exit 0 ready, 3 needs bootstrap
```

It prints `status=ready|missing|stale|uv-missing` plus the venv path and the
exact bootstrap command. `stale` means the venv was built from different
`pyproject.toml` metadata and would run outdated code. `venv_status` and `uv`
are reported separately, so a usable venv reports `ready` even without `uv`
installed.

Portable environment variables prefer `CONTEXT_KIT_DATA`,
`CONTEXT_KIT_EMBED_MODEL`, and `CONTEXT_KIT_OLLAMA_HOST`; Claude
plugin variables remain supported as fallbacks.

## Use

```bash
indexkit index /path/to/vault --name notes                  # build/update the index (incremental)
indexkit query "how did we handle retry backoff" --name notes --k 8
indexkit query "retry backoff" --name notes --k 8 --hybrid
indexkit status --name notes                                # counts, model, dim, FTS5 capability
indexkit list                                               # known indexes
indexkit remove --name notes --yes                          # permanently remove one named index
```

Re-running `index` re-embeds only changed files (content hash). Results report
`path > heading` + a snippet; JSON adds source offsets and retrieval-signal
metadata. Follow up with `rg` to pin exact lines.

`remove` is non-interactive and refuses to run without `--yes`. It accepts the
same safe index names as `index`, `query`, and `status`, removes only that named
index's flat artifact directory, and fails clearly when the index is missing or
cleanup is incomplete. These operations share a per-index process lock, so
removal also refuses while the index is in use.

## Hybrid retrieval (compose semantic + lexical modalities)

Semantic-only is the default. Add `--hybrid` to fuse turbovec and SQLite FTS5/BM25
candidates with deterministic RRF: `1.0 / (60 + semantic_rank) + 1.0 / (60 +
lexical_rank)`. Each source retrieves `3 × k` candidates before final fusion.
`indexkit status` reports the `fts5` capability; if unavailable, `--hybrid` fails
clearly while semantic queries keep working.

Pipe a candidate file set into `--allowlist -` to limit both sources:

```bash
# From the obsidian bridge (graph/tags), or any tool that emits file paths:
obsidian backlinks file="Project X" | indexkit query "open risks" --name notes --hybrid --allowlist -
rg -l '#decision' "$VAULT" | indexkit query "why did we choose X" --name notes --hybrid --allowlist -
```

`indexkit` is not rtk-wrapped, so `rtk indexkit …` is a no-op (passes through). When `rtk`
is installed, prefix the surrounding `rg` step instead — `rtk rg -l` keeps `-l`
raw, so the piped paths above stay intact.

## When NOT to use

For exact tokens/identifiers or code structure, prefer `code-search` (`rg`/`sg`) —
it's faster and more precise. Reach for RAG when meaning ≠ words or the corpus is
large/unfamiliar prose. See the `retrieval-strategy` skill to choose/compose.
