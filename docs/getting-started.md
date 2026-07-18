# Getting started

`context-kit` is a plugin **marketplace** that three hosts install from
**directly** — the same plugins, from a single Markdown source, with no manual
copying of skill folders.

| Host | Register the marketplace | Install a plugin |
| --- | --- | --- |
| **GitHub Copilot CLI** | `copilot plugin marketplace add mbeacom/context-kit` | `copilot plugin install <name>@context-kit` |
| **APM** | `apm marketplace add mbeacom/context-kit` | `apm install <name>@context-kit` |
| **Claude Code** | `/plugin marketplace add mbeacom/context-kit` | `/plugin install <name>@context-kit` |

Installing `code-search` (or `verify`) automatically pulls in the
[`retrieval-core`](plugins/retrieval-core.md) spine.

## Install the plugins

Pick the host you use. Installing `code-search` first is a good default — it
brings the retrieval spine with it.

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit

    copilot plugin install code-search@context-kit      # auto-installs retrieval-core
    copilot plugin install local-rag@context-kit
    copilot plugin install obsidian@context-kit
    copilot plugin install plan-execute@context-kit
    copilot plugin install context-steering@context-kit
    copilot plugin install verify@context-kit           # auto-installs retrieval-core
    copilot plugin install plugin-forge@context-kit
    ```

    Manage them with `copilot plugin list`, `copilot plugin update <name>`, and
    `copilot plugin uninstall <name>`. See the
    [GitHub Copilot guide](GITHUB_COPILOT.md) for details.

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit

    apm install code-search@context-kit      # also pulls retrieval-core (the spine)
    apm install local-rag@context-kit
    apm install obsidian@context-kit
    apm install plan-execute@context-kit
    apm install context-steering@context-kit
    apm install verify@context-kit           # also pulls retrieval-core
    apm install plugin-forge@context-kit
    ```

    APM adds a committed lockfile, a pre-install security scan, transitive
    dependency resolution, and cross-harness deploy. See the
    [APM guide](APM.md).

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit

    /plugin install code-search@context-kit      # lexical/structural/data/history search
    /plugin install local-rag@context-kit         # local semantic search (turbovec + ollama)
    /plugin install obsidian@context-kit           # Obsidian vault → RAG bridge
    /plugin install plan-execute@context-kit       # plan-big / execute-small orchestration
    /plugin install context-steering@context-kit   # place guidance at the cheapest layer
    /plugin install verify@context-kit             # read-only claim verification
    /plugin install plugin-forge@context-kit       # author portable plugins
    ```

## Requirements

The skills degrade gracefully and tell you what's missing. Nothing here calls a
cloud service.

<div class="grid cards" markdown>

-   :material-magnify:{ .lg .middle } **code-search**

    ---

    Needs `rg` (ripgrep); everything else is optional. Run
    `bash plugins/code-search/scripts/check-tools.sh` from a clone to see what's
    installed and the `brew install …` line for the rest.

-   :material-database-search:{ .lg .middle } **local-rag**

    ---

    Needs [`uv`](https://docs.astral.sh/uv/) and a running
    [ollama](https://ollama.com) with an embedding model
    (`ollama pull nomic-embed-text`). GitHub Copilot and APM users bootstrap the
    `rag` CLI once (below); Claude Code auto-bootstraps it.

-   :material-notebook-outline:{ .lg .middle } **obsidian**

    ---

    Optional: the official `obsidian` CLI (with Obsidian running) for
    graph-accurate queries; otherwise it falls back to `rg`/`fd`. Set your vault
    with `CONTEXT_KIT_OBSIDIAN_VAULT`.

</div>

!!! tip "Check your toolbox"

    Run the bundled checker from a clone of the repository to see which optional
    CLIs are present and the exact `brew install …` command for the gaps:

    ```bash
    bash plugins/code-search/scripts/check-tools.sh
    ```

## Bootstrap local-rag outside Claude Code

`local-rag`'s `rag` CLI runs on a uv-managed virtualenv. Claude Code bootstraps
it automatically via a `SessionStart` hook; **GitHub Copilot and APM do not run
Claude hooks**, so bootstrap it once yourself from a clone of this repo:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit/local-rag"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"

ollama pull nomic-embed-text
```

Portable environment variables (Claude Code's `CLAUDE_PLUGIN_*` names remain
supported as fallbacks):

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage for `local-rag` | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |
| `CONTEXT_KIT_OBSIDIAN_VAULT` | vault path for `obsidian` examples/fallbacks | `CLAUDE_PLUGIN_OPTION_VAULT_PATH` |

## Your first search

Once a plugin is installed, ask your agent naturally — the routing agent loads the
right skill for the task:

- "Use the retrieval strategy to find where retry backoff is handled."
- "Use code-search to find structural React `useEffect` cleanup issues."
- "Use local-rag to query my notes for billing open questions."
- "Use the Obsidian RAG bridge to search notes linked to Project X."

### Semantic search with local-rag

```bash
ollama pull nomic-embed-text                 # once
rag index /path/to/vault --name notes        # build/update (incremental)
rag query "open questions about billing" --name notes --k 8
rag status --name notes                       # counts, model, dim
```

### Hybrid retrieval — the payoff

Narrow with the graph or lexical signals, then rerank with vectors:

```bash
# Obsidian graph → semantic rerank (official CLI)
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -

# rg fallback when Obsidian isn't running
VAULT="${CONTEXT_KIT_OBSIDIAN_VAULT:-.}"
rg -l '#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

`rag` returns `path > heading` + a snippet; follow up with `rg` to pin exact lines.

## Next steps

<div class="grid cards" markdown>

- :material-sitemap-outline: **[Architecture](ARCHITECTURE.md)** — the modality
  model and how the plugins compose.
- :material-view-grid-outline: **[Plugins](plugins/index.md)** — a page for each
  plugin in the catalog.
- :material-github: **[Contributing](contributing.md)** — validate, lint, and
  test the marketplace.

</div>
