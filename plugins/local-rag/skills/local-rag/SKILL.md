---
name: local-rag
description: "Use for semantic search over a markdown corpus when keywords aren't enough (you know the meaning/intent, not the exact words), or to build context from a notes vault. Index once, then query; supports hybrid retrieval via an allowlist of candidate files."
license: MIT
compatibility: "Requires the bin/rag CLI (auto-bootstrapped via uv) plus a running ollama with an embedding model pulled (default nomic-embed-text)."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(rag:*) Bash(ollama:*) Read Glob Grep
---

# Local RAG

Fully-local semantic search: `rag` chunks + embeds a corpus (ollama) and indexes
it with turbovec. Nothing leaves the machine.

## Prerequisites

- `ollama serve` running and the model pulled: `ollama pull nomic-embed-text`.
- The `rag` CLI is bootstrapped automatically on session start (uv venv). If
  `rag` is missing, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/bootstrap.sh"`.

## Use

```bash
rag index /path/to/vault --name notes      # build/update the index (incremental)
rag query "how did we handle retry backoff" --name notes --k 8
rag status --name notes                     # counts, model, dim, staleness
rag list                                    # known indexes
```

Re-running `index` re-embeds only changed files (content hash). Results report
`path > heading` + a snippet; follow up with `rg` to pin exact lines.

## Hybrid retrieval (compose with other modalities)

Pipe a candidate file set into `--allowlist -` to rerank only those files
semantically (turbovec allowlist):

```bash
# From the obsidian bridge (graph/tags), or any tool that emits file paths:
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -
rg -l '#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

## When NOT to use

For exact tokens/identifiers or code structure, prefer `code-search` (`rg`/`sg`) —
it's faster and more precise. Reach for RAG when meaning ≠ words or the corpus is
large/unfamiliar prose. See the `retrieval-strategy` skill to choose/compose.
