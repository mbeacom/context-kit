---
name: obsidian-rag-bridge
description: "Use to retrieve from an Obsidian vault by combining its link graph/tags with local semantic search: produce a candidate note set (official obsidian CLI, or rg fallback) and feed it to local-rag's --allowlist. For writing notes, Bases, or Canvas, use the kepano/obsidian-skills plugin instead."
license: MIT
compatibility: "Best with the official obsidian CLI (Obsidian running). Falls back to rg/fd over the vault. Pairs with the local-rag plugin."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(obsidian:*) Bash(rag:*) Bash(rg:*) Bash(rtk rg:*) Bash(fd:*) Read Glob Grep
---

# Obsidian RAG Bridge

Compose Obsidian's graph with semantic search. The pattern: **narrow to candidate
notes via the graph/tags, then rerank semantically with `rag`.**

## 1. Get candidate notes

**Preferred — official `obsidian` CLI** (requires Obsidian running; see
`obsidian help` and <https://help.obsidian.md/cli>):

```bash
obsidian backlinks file="Project X"      # notes linking to a note
obsidian search query="retry policy"     # full-text candidates
obsidian tags                            # explore tags
```

Extract note paths from the output to feed step 2.

**Fallback — `rg`/`fd`** (Obsidian not running / no CLI). Operates on files
directly; note the limitations (won't resolve aliases or `[[link#heading]]`):

```bash
VAULT="${CONTEXT_KIT_OBSIDIAN_VAULT:-${CLAUDE_PLUGIN_OPTION_VAULT_PATH:-.}}"
rg -l '\[\[Project X' "$VAULT"           # approx backlinks
rg -l '(^|\s)#decision' "$VAULT"         # notes with a tag
fd -e md . "$VAULT"                      # all notes
```

> If `rtk` is installed, `rtk rg -l …` compacts output while keeping `-l` raw,
> so the piped note paths in step 2 stay intact. `obsidian` and `rag` aren't
> rtk-wrapped — they pass through unchanged.

## 2. Rerank semantically

Pipe candidate paths into `local-rag`'s allowlist:

```bash
obsidian backlinks file="Project X" | rag query "open risks and mitigations" --name notes --allowlist -
rg -l '(^|\s)#decision' "$VAULT"        | rag query "why did we choose X"      --name notes --allowlist -
```

(Index the vault first: `rag index "$VAULT" --name notes`.)

## 3. Pin exact lines

`rag` returns `path > heading` + snippet. Use `rg` to jump to the exact lines.

## Scope

This plugin only bridges retrieval. For **authoring** Obsidian notes, **Bases**,
or **Canvas**, install [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills)
(the Obsidian founder's MIT skills) and use the official `obsidian` CLI.
