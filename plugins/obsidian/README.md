# Obsidian RAG Bridge

A skill-only retrieval bridge for Claude Code and GitHub Copilot that connects
an Obsidian vault to local semantic search. The pattern: **narrow to candidate
notes via the vault's link graph or tags, then rerank semantically with `rag`.**

No bundled binary, no Python deps — just shell commands and the `obsidian-rag-bridge`
skill.

## How it works

```text
obsidian backlinks / rg tag search
          │
          ▼  candidate note paths
    rag query --allowlist -
          │
          ▼  ranked results (path > heading + snippet)
```

1. **Produce candidates** — use the official `obsidian` CLI (requires Obsidian
   running) or fall back to `rg`/`fd` directly over vault files.
2. **Rerank semantically** — pipe candidate paths to `rag query --allowlist -`,
   which runs hybrid search only over that file set.
3. **Pin exact lines** — use `rg` on the returned `path > heading` hits.

## Prerequisites

- **`local-rag` plugin** (required) — provides the `rag` CLI. Index your vault
  once with:

  ```bash
  rag index /path/to/vault --name notes
  ```

- **Official `obsidian` CLI** (optional, recommended) — ships with Obsidian
  desktop. Enables graph-aware backlink and full-text queries. See
  <https://help.obsidian.md/cli> and `obsidian help`.

- **`rg` / `fd`** (fallback) — used when Obsidian is not running or the CLI is
  unavailable. Operates on files directly; won't resolve wikilink aliases or
  `[[link#heading]]` fragments.

## Quick usage

```bash
# Graph-aware (official CLI)
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -

# Tag-based fallback (rg)
VAULT="${CONTEXT_KIT_OBSIDIAN_VAULT:-${CLAUDE_PLUGIN_OPTION_VAULT_PATH:-.}}"
rg -l '(^|\s)#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

## Scope and out-of-scope

This plugin **only bridges retrieval**.

For **authoring** Obsidian notes, **Bases**, or **Canvas**, install
[`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) (the
Obsidian founder's MIT-licensed skills) and use the official `obsidian` CLI.

## Skills

| Skill | Purpose |
|---|---|
| `obsidian-rag-bridge` | Graph/tag → `rag --allowlist` retrieval |

---

MIT © Mark Beacom
