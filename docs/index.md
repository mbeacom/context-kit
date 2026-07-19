---
hide:
  - navigation
  - toc
---

<div class="ck-hero" markdown>

# context-kit

<p class="ck-tagline">
Context-engineering plugins for GitHub Copilot, APM, and Claude Code — get the
right information in front of your agent, and keep the wrong information out.
</p>

<div class="ck-badges" markdown>
![License](https://img.shields.io/badge/License-MIT-4f46e5)
![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-plugin-6366f1)
![APM](https://img.shields.io/badge/APM-package-6366f1)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6366f1)
![Local first](https://img.shields.io/badge/Local-first-22c55e)
</div>

[Get started :material-rocket-launch-outline:](getting-started.md){ .md-button .md-button--primary }
[Follow a recipe :material-chef-hat:](cookbook.md){ .md-button }
[Review trust boundaries :material-shield-lock-outline:](security.md){ .md-button }

</div>

---

`context-kit` is a context-engineering plugin pack for **GitHub Copilot CLI**,
**APM** (Agent Package Manager), and [Claude Code](https://code.claude.com). Its
spine is a set of complementary **retrieval modalities** — lexical, structural,
code-intelligence, structured-data, history, semantic (RAG), graph, and durable
memory — plus a routing agent that picks and composes them. Default workflows
keep indexes and reviewed records on your machine; configured model endpoints,
providers, and allowlisted commands can reach external systems. Around that
retrieval spine, eleven shipped plugins add
orchestration, steering, read-only verification and change-impact analysis,
controlled runtime evidence, cross-session handoff, and authoring quality.

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

    `local-rag` chunks and embeds a corpus with **ollama**, indexes it with
    **turbovec**, and can fuse FTS5/BM25 lexical candidates with vectors using
    deterministic reciprocal-rank fusion.

    [:octicons-arrow-right-24: local-rag](plugins/local-rag.md)

-   :material-source-branch:{ .lg .middle } **One source, three hosts**

    ---

    The same plugins install directly into GitHub Copilot CLI
    (`copilot plugin`), Microsoft's APM (`apm install`), and Claude Code
    (`/plugin`) — no manual copying of skill folders.

    [:octicons-arrow-right-24: Getting started](getting-started.md)

-   :material-scale-balance:{ .lg .middle } **Spend tokens where they count**

    ---

    `plan-execute` keeps planning frontier-quality and delegates bulky work to
    a cheaper executor. `context-steering` places each rule at the cheapest
    layer that still fires.

    [:octicons-arrow-right-24: plan-execute](plugins/plan-execute.md)

-   :material-check-decagram-outline:{ .lg .middle } **Verify before you trust**

    ---

    A read-only `verifier` checks repository claims with `file:line` evidence,
    while `/analyze-impact` maps a proposed change's prospective blast radius
    without implementing or executing it.

    [:octicons-arrow-right-24: verify](plugins/verify.md)

-   :material-pulse:{ .lg .middle } **Escalate to runtime evidence**

    ---

    `runtime-evidence` runs only exact, pre-reviewed command IDs from a
    user-owned allowlist when static verification cannot settle a runtime claim,
    then returns bounded artifacts to `verify`.

    [:octicons-arrow-right-24: runtime-evidence](plugins/runtime-evidence.md)

-   :material-swap-horizontal:{ .lg .middle } **Carry context across sessions**

    ---

    `context-handoff` manually writes and resumes bounded, verified task state,
    validating repository identity and freshness before saved claims are trusted.

    [:octicons-arrow-right-24: context-handoff](plugins/context-handoff.md)

-   :material-head-cog-outline:{ .lg .middle } **Recall durable project memory**

    ---

    `memory` preserves reviewed evidence, primary memories, cue anchors,
    freshness, and supersession. An optional MemPalace adapter adds
    project-isolated provider recall and opt-in lifecycle capture.

    [:octicons-arrow-right-24: memory](plugins/memory.md)

-   :material-hammer-wrench:{ .lg .middle } **Author more like these**

    ---

    `plugin-forge` scaffolds portable plugins, keeps manifests in lockstep, and
    enforces a deterministic catalog discovery-quality budget.

    [:octicons-arrow-right-24: plugin-forge](plugins/plugin-forge.md)

</div>

## Install in seconds

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

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install code-search@context-kit   # auto-installs retrieval-core
    ```

See [Getting started](getting-started.md) for the full plugin list, requirements,
and your first search.

## Operate with clear boundaries

<div class="grid cards" markdown>

- :material-chef-hat: **[Cookbook](cookbook.md)** — six task-oriented journeys
  that compose retrieval, verification, continuity, and orchestration.
- :material-shield-lock-outline: **[Security and trust](security.md)** — decide
  what can execute, what leaves the process, and where retained data lives.
- :material-lifebuoy: **[Troubleshooting and lifecycle](troubleshooting.md)** —
  verify first run, diagnose refusal modes, update safely, and uninstall.

</div>

## Pick a modality by what you know

| You know… | Modality | Example |
| --- | --- | --- |
| an exact token / regex / filename | lexical | `rg -t py 'def login'` · `fd -e ts` |
| the code *shape*, not the text | structural | `sg -p 'logger.debug($$$)' --lang js` |
| the *symbol* — its defs / refs / callers | code-intelligence | `global -xr parseConfig` · `ctags -R` |
| a JSON/YAML schema path | structured-data | `jq '.scripts' package.json` |
| *when / why* code changed | history | `git log -S'retry' -- src/` |
| only the *meaning / intent* | semantic (RAG) | `rag query "how do we handle backoff" --name notes` |
| the corpus is an Obsidian vault | graph | `obsidian backlinks file="Project X"` |
| a prior decision, constraint, procedure, or episode | durable memory | `/recall-memory "why did we change retries?"` |

The [`retrieval-strategist`](plugins/retrieval-core.md) agent (or the
`retrieval-strategy` skill) chooses which one fits — and they **compose**.
