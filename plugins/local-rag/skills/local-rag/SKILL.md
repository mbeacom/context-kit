---
name: local-rag
description: "Use for semantic search over a markdown corpus when keywords aren't enough (you know the meaning/intent, not the exact words), or opt-in hybrid semantic plus lexical search when both meaning and exact terms matter. Index once, then query."
license: MIT
compatibility: "Requires the bin/rag CLI (auto-bootstrapped via uv) plus a running ollama with an embedding model pulled (default nomic-embed-text)."
metadata:
  author: Mark Beacom
  version: "0.2.0"
allowed-tools: Bash(rag:*) Bash(ollama:*) Bash(rg:*) Bash(rtk rg:*) Read Glob Grep
---

# Local RAG

Fully-local semantic search: `rag` chunks + embeds a corpus (ollama) and indexes
it with turbovec. Nothing leaves the machine.

## Prerequisites

- `ollama serve` running and the model pulled: `ollama pull nomic-embed-text`.
- Claude Code: the `rag` CLI is bootstrapped automatically on session start
  (uv venv). If `rag` is missing, run
  `bash "${CLAUDE_PLUGIN_ROOT}/scripts/bootstrap.sh"`.
- GitHub Copilot/manual: clone this repo, set `CONTEXT_KIT_DATA`, run
  `plugins/local-rag/scripts/bootstrap.sh`, and add `plugins/local-rag/bin` to
  `PATH`.

Portable environment variables prefer `CONTEXT_KIT_DATA`,
`CONTEXT_KIT_EMBED_MODEL`, and `CONTEXT_KIT_OLLAMA_HOST`; Claude
plugin variables remain supported as fallbacks.

## Use

```bash
rag index /path/to/vault --name notes      # build/update the index (incremental)
rag query "how did we handle retry backoff" --name notes --k 8
rag query "retry backoff" --name notes --k 8 --hybrid
rag status --name notes                     # counts, model, dim, FTS5 capability
rag list                                    # known indexes
```

Re-running `index` re-embeds only changed files (content hash). Results report
`path > heading` + a snippet; JSON adds source offsets and retrieval-signal
metadata. Follow up with `rg` to pin exact lines.

## Hybrid retrieval (compose semantic + lexical modalities)

Semantic-only is the default. Add `--hybrid` to fuse turbovec and SQLite FTS5/BM25
candidates with deterministic RRF: `1.0 / (60 + semantic_rank) + 1.0 / (60 +
lexical_rank)`. Each source retrieves `3 × k` candidates before final fusion.
`rag status` reports the `fts5` capability; if unavailable, `--hybrid` fails
clearly while semantic queries keep working.

Pipe a candidate file set into `--allowlist -` to limit both sources:

```bash
# From the obsidian bridge (graph/tags), or any tool that emits file paths:
obsidian backlinks file="Project X" | rag query "open risks" --name notes --hybrid --allowlist -
rg -l '#decision' "$VAULT" | rag query "why did we choose X" --name notes --hybrid --allowlist -
```

`rag` is not rtk-wrapped, so `rtk rag …` is a no-op (passes through). When `rtk`
is installed, prefix the surrounding `rg` step instead — `rtk rg -l` keeps `-l`
raw, so the piped paths above stay intact.

## When NOT to use

For exact tokens/identifiers or code structure, prefer `code-search` (`rg`/`sg`) —
it's faster and more precise. Reach for RAG when meaning ≠ words or the corpus is
large/unfamiliar prose. See the `retrieval-strategy` skill to choose/compose.
