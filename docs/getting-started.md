# Getting started

`context-kit` is a plugin **marketplace** that three hosts install from
**directly** — the same plugins, from a single Markdown source, with no manual
copying of skill folders.

| Host | Register the marketplace | Install a plugin |
| --- | --- | --- |
| **GitHub Copilot CLI** | `copilot plugin marketplace add mbeacom/context-kit` | `copilot plugin install <name>@context-kit` |
| **APM** | `apm marketplace add mbeacom/context-kit` | `apm install <name>@context-kit` |
| **Claude Code** | `/plugin marketplace add mbeacom/context-kit` | `/plugin install <name>@context-kit` |

Installing `code-search` or `verify` automatically pulls in the
[`retrieval-core`](plugins/retrieval-core.md) spine. `runtime-evidence` and
`context-handoff` depend on `verify`, so either pulls `verify` and then
`retrieval-core` transitively. `memory` depends on `context-handoff`, so it pulls
the complete continuity and verification chain.

## Install the plugins

Pick the host you use. Install one entry plugin for the journey you need rather
than the entire catalog. `code-search` is a good first choice and brings the
retrieval spine with it.

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install code-search@context-kit
    ```

    See the [GitHub Copilot guide](GITHUB_COPILOT.md) for host configuration and
    the [lifecycle guide](troubleshooting.md) for verification, updates, and
    uninstall.

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install code-search@context-kit
    ```

    APM adds a project lockfile, dependency resolution, target deployment, and
    audit/policy checks. See the [APM guide](APM.md).

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install code-search@context-kit
    ```

    Run `/reload-plugins`, then inspect `/plugin` → **Installed** or
    `claude plugin list --json`.

Choose an entry plugin:

| Journey | Install | Also needed at runtime |
| --- | --- | --- |
| Search code, data, or docs | `code-search` | `rg`; optional search CLIs |
| Search a corpus semantically | `local-rag` | uv, Ollama, embedding model |
| Narrow an Obsidian vault, then rerank | `obsidian` + `local-rag` | Obsidian CLI or `rg`/`fd` |
| Verify repository claims | `verify` | — |
| Verify, then observe runtime behavior | `runtime-evidence` | Python 3, POSIX, reviewed allowlist |
| Verify, then hand off | `context-handoff` | Python 3 |
| Recall durable project memory | `memory` | Python 3; MemPalace optional |
| Plan, then delegate execution | `plan-execute` | A host with the required workflow/subagent support |
| Choose where context belongs | `context-steering` | — |
| Author portable plugins | `plugin-forge` | validation toolchain for maintainers |

See [Plugins](plugins/index.md) for every component and dependency, or start
from a complete [cookbook journey](cookbook.md).

## Requirements

The skills degrade gracefully and tell you what's missing. Default storage is
local, but a configured model endpoint, provider, or user-allowlisted command
may access a network or other external state. Allowlisting does not prove a
command has no side effects.

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

-   :material-language-python:{ .lg .middle } **runtime and handoff tools**

    ---

    `runtime-evidence` and `context-handoff` require Python 3. Both use only the
    standard library. The runtime runner requires POSIX and refuses Windows
    before execution; the handoff validator is cross-platform. Runtime evidence
    also requires a user-owned exact-ID JSON allowlist; handoffs default to
    `.context-kit/handoff.md`.

-   :material-head-cog-outline:{ .lg .middle } **memory**

    ---

    Needs Python 3 for local reviewed records. Optional provider recall uses a
    separately installed MemPalace CLI (`uv tool install mempalace`). Automatic
    capture is disabled by default and requires an explicit project scope.

</div>

!!! tip "Check your toolbox"

    Run the bundled checker from a clone of the repository to see which optional
    CLIs are present and the exact `brew install …` command for the gaps:

    ```bash
    bash plugins/code-search/scripts/check-tools.sh
    ```

## Complete first-run setup

Verify installation with the host-specific checks in
[Troubleshooting and lifecycle](troubleshooting.md#verify-installation-by-host).
GitHub Copilot and APM do not run Claude hooks, so `local-rag` needs one manual
bootstrap from a clone:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
ollama pull nomic-embed-text
rag list
```

Use `CONTEXT_KIT_*` variables in portable profiles. The
[GitHub Copilot guide](GITHUB_COPILOT.md#running-local-rag-outside-claude-code)
contains the canonical cross-host variable table, and each plugin page documents
its own defaults and Claude fallback.

Before configuring a remote Ollama host, runtime allowlist, memory provider, or
Claude lifecycle hooks, read [Security and trust boundaries](security.md).

## Run a first journey

Once a plugin is installed, ask your agent naturally — the routing agent loads the
right skill for the task:

- "Use the retrieval strategy to find where retry backoff is handled."
- "Use code-search to find structural React `useEffect` cleanup issues."
- "Use local-rag to query my notes for billing open questions."
- "Use the Obsidian RAG bridge to search notes linked to Project X."
- "Analyze the change impact of renaming this event field."
- "Collect runtime evidence for this unable-to-check health endpoint claim."
- "Write a handoff before I continue this task in another session."
- "Recall why this project changed its retry policy, then verify the source."

The key habit is **retrieve, then pin**: use search to find candidates, open the
primary file, and cite exact lines before relying on the answer. The
[cookbook](cookbook.md) walks through that flow plus graph/rerank,
verify/observe, verify/handoff, recall/verify, and plan/execute.

## Next steps

<div class="grid cards" markdown>

- :material-sitemap-outline: **[Architecture](ARCHITECTURE.md)** — the modality
  model and how the plugins compose.
- :material-chef-hat: **[Cookbook](cookbook.md)** — task-oriented multi-plugin
  journeys.
- :material-shield-lock-outline: **[Security](security.md)** — trust boundaries,
  retained data, hooks, providers, and command execution.
- :material-lifebuoy: **[Troubleshooting](troubleshooting.md)** — first-run
  checks, refusal modes, updates, uninstall, and data locations.
- :material-view-grid-outline: **[Plugins](plugins/index.md)** — a page for each
  plugin in the catalog.
- :material-github: **[Contributing](contributing.md)** — validate, lint, and
  test the marketplace.

</div>
