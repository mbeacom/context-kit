---
hide:
  - navigation
  - toc
---

<div class="ck-hero" markdown>

# context-kit

<p class="ck-tagline">
Context-engineering plugins for Claude Code, GitHub Copilot, and APM — get the
right information in front of your agent, and keep the wrong information out.
</p>

<div class="ck-badges" markdown>
![License](https://img.shields.io/badge/License-MIT-4f46e5)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6366f1)
![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-plugin-6366f1)
![APM](https://img.shields.io/badge/APM-package-6366f1)
![Local first](https://img.shields.io/badge/Local-first-22c55e)
</div>

[Get started :material-rocket-launch-outline:](getting-started.md){ .md-button .md-button--primary }
[Browse the plugins :material-view-grid-outline:](plugins/index.md){ .md-button }

</div>

---

`context-kit` is a [Claude Code](https://code.claude.com) plugin **marketplace**
and a GitHub Copilot-compatible **Agent Skills** pack for **context
engineering**. Its spine is a set of complementary **retrieval modalities** —
lexical, structural, structured-data, history, semantic (RAG), and graph — plus
a routing agent that picks and composes them. Everything runs **locally**; the
RAG layer keeps your corpus on your machine.

## Why context-kit

<div class="grid cards" markdown>

-   :material-map-search-outline:{ .lg .middle } **Retrieval, done right**

    ---

    A routing agent picks the cheapest modality that answers the question —
    exact-token, code-shape, schema-path, git history, or meaning — and
    **composes** them: narrow lexically, rerank by vectors, pin exact lines.

    [:octicons-arrow-right-24: Architecture](ARCHITECTURE.md)

-   :material-laptop:{ .lg .middle } **Local-first semantic search**

    ---

    `local-rag` chunks and embeds a corpus with **ollama** and indexes it with
    **turbovec**. No cloud calls, no API keys — your notes and code never leave
    the machine.

    [:octicons-arrow-right-24: local-rag](plugins/local-rag.md)

-   :material-source-branch:{ .lg .middle } **One source, three hosts**

    ---

    The same plugins install directly into Claude Code (`/plugin`), GitHub
    Copilot CLI (`copilot plugin`), and Microsoft's APM (`apm install`) — no
    manual copying of skill folders.

    [:octicons-arrow-right-24: Getting started](getting-started.md)

-   :material-scale-balance:{ .lg .middle } **Spend tokens where they count**

    ---

    `plan-execute` keeps planning frontier-quality and delegates bulky work to
    a cheaper executor. `context-steering` places each rule at the cheapest
    layer that still fires.

    [:octicons-arrow-right-24: plan-execute](plugins/plan-execute.md)

-   :material-check-decagram-outline:{ .lg .middle } **Verify before you trust**

    ---

    A read-only `verifier` subagent checks AI answers, plans, and PR
    descriptions against the actual repository and returns per-claim verdicts
    with `file:line` evidence.

    [:octicons-arrow-right-24: verify](plugins/verify.md)

-   :material-hammer-wrench:{ .lg .middle } **Author more like these**

    ---

    `plugin-forge` scaffolds portable plugins and keeps `plugin.json` and
    `apm.yml` in lockstep — the same toolkit used to build this marketplace.

    [:octicons-arrow-right-24: plugin-forge](plugins/plugin-forge.md)

</div>

## Install in seconds

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install code-search@context-kit   # auto-installs retrieval-core
    ```

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install code-search@context-kit   # auto-installs retrieval-core
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install code-search@context-kit   # also pulls retrieval-core
    ```

See [Getting started](getting-started.md) for the full plugin list, requirements,
and your first search.

## Pick a modality by what you know

| You know… | Modality | Example |
| --- | --- | --- |
| an exact token / regex / filename | lexical | `rg -t py 'def login'` · `fd -e ts` |
| the code *shape*, not the text | structural | `sg -p 'logger.debug($$$)' --lang js` |
| a JSON/YAML schema path | structured-data | `jq '.scripts' package.json` |
| *when / why* code changed | history | `git log -S'retry' -- src/` |
| only the *meaning / intent* | semantic (RAG) | `rag query "how do we handle backoff" --name notes` |
| the corpus is an Obsidian vault | graph | `obsidian backlinks file="Project X"` |

The [`retrieval-strategist`](plugins/retrieval-core.md) agent (or the
`retrieval-strategy` skill) chooses which one fits — and they **compose**.
