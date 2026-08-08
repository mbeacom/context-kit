# Plugins

The marketplace ships fourteen plugins. The **spine** is retrieval — a routing
agent that picks and composes modalities — surrounded by plugins for
orchestration, steering, verification and impact analysis, multi-lens review,
exhaustive corpus review, controlled runtime evidence, token economics,
cross-session handoff, and authoring.

!!! tip "Start from the task"
    Use the [cookbook](../cookbook.md) for multi-plugin journeys, the
    [security guide](../security.md) before enabling execution or retention, and
    [troubleshooting](../troubleshooting.md) for first-run and lifecycle work.

<div class="grid cards" markdown>

-   :material-map-search-outline:{ .lg .middle } **[retrieval-core](retrieval-core.md)**

    ---

    The spine: a `retrieval-strategist` agent + `retrieval-strategy` skill that
    choose and compose modalities. Other plugins depend on it.

    `retrieval` · shipped

-   :material-magnify:{ .lg .middle } **[code-search](code-search.md)**

    ---

    Lexical, structural, code-intelligence, structured-data, history, rewrite,
    metrics, and non-code doc search. Two skills split by corpus.

    `retrieval` · shipped

-   :material-database-search:{ .lg .middle } **[indexkit](indexkit.md)**

    ---

    Local-first semantic RAG: a `bin/indexkit` CLI with a configurable Ollama
    endpoint, turbovec vectors, opt-in FTS5/BM25 reciprocal-rank fusion, and
    hybrid `--allowlist` retrieval.

    `retrieval` · shipped

-   :material-notebook-outline:{ .lg .middle } **[obsidian](obsidian.md)**

    ---

    Skill-only RAG bridge: turn a vault's graph and tags into a candidate set
    fed to `indexkit`.

    `retrieval` · shipped

-   :material-scale-balance:{ .lg .middle } **[plan-execute](plan-execute.md)**

    ---

    Plan-big / execute-small orchestration: a strong model plans and delegates
    token-heavy work to a cheaper executor.

    `orchestration` · shipped

-   :material-tune-variant:{ .lg .middle } **[context-steering](context-steering.md)**

    ---

    Place guidance at the cheapest layer that still fires — memory, rules,
    skills, subagents, MCP servers, or hooks.

    `steering` · shipped

-   :material-check-decagram-outline:{ .lg .middle } **[verify](verify.md)**

    ---

    Read-only per-claim verification plus prospective change-impact and
    blast-radius analysis, with an enforced non-mutating inspection runner.

    `verification` · shipped

-   :material-pulse:{ .lg .middle } **[runtime-evidence](runtime-evidence.md)**

    ---

    Controlled runtime observation after static verification cannot settle a
    claim, using exact allowlisted command IDs with bounded artifacts — or an
    approved optional tool when no command fits.

    `verification` · shipped

-   :material-clipboard-check-multiple-outline:{ .lg .middle } **[corpus-review](corpus-review.md)**

    ---

    Exhaustive review of a corpus too large to read at once — hashed unit
    inventory, bounded resumable shards, and a provable coverage ledger.

    `verification` · shipped

-   :material-account-search-outline:{ .lg .middle } **[deep-review](deep-review.md)**

    ---

    Multi-lens evaluative critique: independent charters return typed
    findings, agreement merges into confidence, disagreement survives as an
    explicit tradeoff.

    `verification` · shipped

-   :material-swap-horizontal:{ .lg .middle } **[context-handoff](context-handoff.md)**

    ---

    Manual-first, bounded task-state handoffs with a read-only compiler and
    deterministic provenance/freshness validation.

    `continuity` · shipped

-   :material-head-cog-outline:{ .lg .middle } **[memory](memory.md)**

    ---

    Reviewed durable memories with provenance, cue anchors, freshness,
    supersession, and an optional project-isolated MemPalace provider.

    `continuity` · shipped

-   :material-scale-balance:{ .lg .middle } **[token-economics](token-economics.md)**

    ---

    Measure token spend from local host records, and prove a tool's savings
    with a controlled A/B that must preserve the answer.

    `measurement` · shipped

-   :material-hammer-wrench:{ .lg .middle } **[plugin-forge](plugin-forge.md)**

    ---

    Author portable plugins with scaffolding, manifest/frontmatter checks, and a
    deterministic aggregate catalog discovery-quality gate.

    `authoring` · shipped

</div>

## How they fit together

```mermaid
graph TD
    RC[retrieval-core<br/>routing agent + decision flow]
    CS[code-search]
    LR[indexkit]
    OB[obsidian]
    VF[verify]
    RE[runtime-evidence]
    CR[corpus-review]
    DR[deep-review]
    CH[context-handoff]
    MM[memory]
    PE[plan-execute]
    CST[context-steering]
    PF[plugin-forge]

    CS -->|depends on| RC
    VF -->|depends on| RC
    RE -->|depends on| VF
    CH -->|depends on| VF
    MM -->|depends on| CH
    CR -->|depends on| VF
    CR -->|depends on| PE
    DR -->|depends on| VF
    DR -->|depends on| PE
    OB -->|feeds --allowlist| LR
    RC -.composes.-> CS
    RC -.composes.-> LR
    RC -.routes recall to.-> MM
    RC -.routes coverage to.-> CR

    classDef spine fill:#4f46e5,stroke:#4338ca,color:#fff;
    class RC spine;
```

- **`code-search`** and **`verify`** depend on `retrieval-core`.
- **`runtime-evidence`** and **`context-handoff`** depend on `verify`, so
  installing either transitively pulls the spine.
- **`memory`** depends on `context-handoff`, so it also pulls `verify` and the
  retrieval spine. Handoffs remain authoritative current task state; archived
  copies are historical evidence.
- **`corpus-review`** depends on `verify` and `plan-execute`: it raises `verify`'s
  `unable-to-check` discipline from one claim to a whole corpus, and reuses
  `plan-execute`'s cheap-worker fan-out to read shards. Retrieval surfaces the
  relevant; corpus review proves the exhaustive.
- **`deep-review`** depends on `verify` and `plan-execute`: it deliberately
  refuses to settle its own `DEFECT` findings and routes them to `verify` as
  claims, and reuses `plan-execute`'s fan-out to run lenses independently.
  Verification asks whether a claim is true; deep review asks whether the work
  is good.
- **`obsidian`** and **`indexkit`** pair: the bridge produces candidate note
  paths that feed `indexkit`'s hybrid `--allowlist` search.
- **`plan-execute`**, **`context-steering`**, and **`plugin-forge`** are
  independent — orchestration, steering, and authoring around the retrieval core.
  `verify` can optionally use `plan-execute` for broad read-only impact coverage,
  but does not depend on it.

## Dependencies at a glance

| Plugin | Category | Ships | Depends on |
| --- | --- | --- | --- |
| [retrieval-core](retrieval-core.md) | retrieval | agent + skill | — |
| [code-search](code-search.md) | retrieval | 2 skills + tool checker | `retrieval-core` |
| [indexkit](indexkit.md) | retrieval | `bin/indexkit` CLI + skill | ollama + turbovec + SQLite FTS5 for `--hybrid` |
| [obsidian](obsidian.md) | retrieval | skill only | `indexkit` (runtime) |
| [plan-execute](plan-execute.md) | orchestration | skill + command + workflow + subagent | — |
| [context-steering](context-steering.md) | steering | skill + examples | — |
| [verify](verify.md) | verification | subagent + 2 skills + command + stdlib inspection runner | `retrieval-core` |
| [runtime-evidence](runtime-evidence.md) | verification | skill + command + subagent + stdlib runner | `verify` → `retrieval-core` |
| [corpus-review](corpus-review.md) | verification | skill + command + subagent + 3 stdlib scripts | `plan-execute`, `verify` → `retrieval-core` |
| [deep-review](deep-review.md) | verification | skill + command + subagent + stdlib adjudicator | `plan-execute`, `verify` → `retrieval-core` |
| [context-handoff](context-handoff.md) | continuity | skill + 2 commands + subagent + stdlib validator | `verify` → `retrieval-core` |
| [memory](memory.md) | continuity | skill + 4 commands + stdlib adapter + opt-in Claude hooks | `context-handoff` → `verify` → `retrieval-core`; MemPalace optional |
| [token-economics](token-economics.md) | measurement | 2 skills + 2 commands + 2 stdlib scripts | `verify` → `retrieval-core` |
| [plugin-forge](plugin-forge.md) | authoring | skill + command + validators/tests | — |
