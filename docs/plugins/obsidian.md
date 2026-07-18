# obsidian

!!! abstract "Obsidian → RAG bridge"
    A **skill-only** retrieval bridge: narrow to candidate notes via the vault's
    link graph or tags, then rerank semantically with `rag`. No bundled binary,
    no Python deps — just shell commands and the `obsidian-rag-bridge` skill.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install obsidian@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install obsidian@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install obsidian@context-kit
    ```

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

- **[`local-rag`](local-rag.md)** (required) — provides the `rag` CLI. Index your
  vault once: `rag index /path/to/vault --name notes`.
- **Official `obsidian` CLI** (optional, recommended) — ships with Obsidian
  desktop; enables graph-aware backlink and full-text queries.
- **`rg` / `fd`** (fallback) — used when Obsidian isn't running. Operates on files
  directly; won't resolve wikilink aliases or `[[link#heading]]` fragments.

## Quick usage

```bash
# Graph-aware (official CLI)
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -

# Tag-based fallback (rg)
VAULT="${CONTEXT_KIT_OBSIDIAN_VAULT:-.}"
rg -l '(^|\s)#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

Set the vault path via Claude `userConfig` (`vault_path`) or
`CONTEXT_KIT_OBSIDIAN_VAULT` for Copilot/APM/manual usage.

## Scope

!!! warning "Retrieval only"
    This plugin **only bridges retrieval**. For **authoring** Obsidian notes,
    **Bases**, or **Canvas**, install
    [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) (the
    Obsidian founder's MIT-licensed skills) and use the official `obsidian` CLI.

## At a glance

| | |
| --- | --- |
| **Category** | retrieval |
| **Provides** | 1 skill (`obsidian-rag-bridge`), no binaries |
| **Pairs with** | [`local-rag`](local-rag.md) (runtime dependency) |
| **License** | MIT |
