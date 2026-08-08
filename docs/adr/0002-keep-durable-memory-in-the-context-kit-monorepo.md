---
schemaVersion: 0.1.0
id: "0002"
title: "Keep durable memory in the context-kit monorepo"
status: proposed
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [memory, repository-structure, packaging]
scope: org
reversibility: two-way-door
blastRadius: cross-team
relatesTo: ["0001"]
affects:
  - type: path
    pattern: plugins/memory/**
  - type: path
    pattern: plugins/local-rag/**
    note: Memory's semantic provider; the coupling that decides this.
  - type: path
    pattern: plugins/context-handoff/**
    note: Memory's other hard dependency.
  - type: path
    pattern: .claude-plugin/marketplace.json
provenance:
  authoredBy: agent-drafted
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0002: Keep durable memory in the context-kit monorepo

## Context

`plugins/memory` is the largest code artifact in a repository that is otherwise
a catalog of Markdown skills. That size asymmetry recurrently raises the
question of whether it should live in its own repository. The question has been
asked more than once and, absent a record, keeps being answered from scratch.

The intuition behind splitting is reasonable: a 6,905-line Python plugin with
its own MCP server, hook set, and 3,700 lines of tests looks like a project, not
a catalog entry. The relevant question is not whether it is *large* but whether
it is *separable* — whether it has an audience or a release cadence independent
of the catalog.

Measured on 2026-08-08:

| Plugin | Python LOC | Files touched, last 200 commits |
|---|---|---|
| **memory** | 6,905 | 111 (#3) |
| plugin-forge | 4,139 | 140 (#2) |
| corpus-review | 2,815 | — |
| **local-rag** *(memory's dependency)* | 2,261 | **163 (#1)** |

Two facts decide it.

**The dependency arrow points inward.** `memory` hard-depends on
`context-handoff` *and* `local-rag`, declared in both `plugin.json` and
`apm.yml`. Nothing in the catalog depends on `memory` — the only references are
docs, `marketplace.json`, and CI. A split therefore exports two dependencies,
and imports no consumers.

**The coupling is a deployed-filesystem assumption, not just a manifest entry.**
`scripts/memory-provider.py` resolves the rag runtime as a *marketplace sibling*:

```python
sibling = Path(plugin_data).expanduser().parent / "local-rag"
```

Its docstring pins this to a verified real install layout,
`~/.copilot/plugin-data/context-kit/{memory,local-rag}`. Both hosts lay plugin
data out as `<marketplace-root>/<plugin>`. Move `memory` to its own marketplace
and that path resolves under the *new* root, where `local-rag` does not exist —
so it degrades silently to the documented default.

**Cadence is the disqualifier.** `memory` is not the fastest-moving plugin; its
own dependency is. A separate repo would spend its life chasing `local-rag`
releases across a repo boundary, converting a same-commit refactor into a
version-matrix negotiation. Splits pay off when the extracted component
stabilizes faster than its host. This one would stabilize *slower*.

## Decision

We will keep `plugins/memory` in the `context-kit` monorepo. If a standalone
artifact is later warranted, we will extract the **MCP server plus the
`context-kit/memory-v1` contract and validator** — not the plugin.

## Options considered

### Option A: Keep memory in the monorepo (chosen)

| Dimension | Assessment |
|---|---|
| Dependency handling | Same-commit refactors across memory + local-rag + handoff |
| Sibling path resolution | Keeps working; verified layout holds |
| Release cadence | One catalog version; no matrix |
| Cost | Repo keeps a large Python component in a Markdown-majority catalog |

### Option B: Split `memory` alone into its own repository

**Pros:** Smaller catalog; memory gets an independent issue tracker and release
cadence; the Python surface stops dominating repo statistics.
**Cons:** Breaks the sibling resolution above. Forces either a cross-repo
version matrix against a *faster-moving* dependency, or demotion of `rag` to an
externally-discovered provider — which costs it the "hard dependency, no
external deps, all criteria met" property that makes it the default semantic
path in `provider-qualification.md`. Also splits
`tests/integration/test_continuity_stack.py`, which exercises memory and handoff
jointly. All cost, no consumer benefit.

### Option C: Split memory *with* `local-rag` and `context-handoff`

**Pros:** Preserves the sibling layout and the integration suite; the extracted
unit is internally coherent — it is the continuity-plus-semantic core.
**Cons:** Moves 3 of 13 plugins, i.e. re-homes the catalog's center of gravity
rather than trimming it. `context-handoff` and `local-rag` have consumers and
meaning outside memory. This is not "splitting out memory"; it is forking the
project into two catalogs and inheriting the routing problem of which one a user
installs.

### Option D: Extract only the MCP server and record contract

**Pros:** The genuinely separable unit. `mcp/server.py` (344 lines) plus the
`memory-v1` contract and validator has no `local-rag` coupling and a real
audience outside this catalog — any agent harness wanting provenance-bound
records.
**Cons:** Premature today; there is no external consumer asking for it. Held
open as the *correct* split if one appears.

### Option E: Do nothing and leave the question open

**Cons:** This is the status quo, and its cost is demonstrated: the question has
now consumed analysis time more than once with no durable answer.

## Trade-offs

- The catalog keeps a component whose LOC is ~1.7x the next largest, so
  repo-level language statistics will keep implying it is a Python project.
- Contributors touching memory must run the cross-plugin integration suite, not
  just the plugin's own tests.
- We accept that if an external consumer for the record contract *does* appear,
  we will have to do Option D's work later, under time pressure rather than at
  leisure.

## Consequences

- **Easier:** refactors that span memory, handoff, and rag land in one commit
  with one version bump; the sibling path assumption stays valid.
- **Harder:** memory cannot be released independently of the catalog.
- **How we would know this was wrong:** a consumer outside `context-kit` adopts
  the `memory-v1` record contract or the MCP server, *or* `local-rag` churn
  drops below memory's for two consecutive quarters (removing the
  chasing-a-faster-dependency objection). Either condition makes Option D live.
- **Revisit if:** either trigger above fires, or `memory` gains a second
  independent consumer inside the catalog.

## Action items

1. [x] Record the measurement that decides this, so it is not re-derived.
2. [ ] Note Option D in `plugins/memory/README.md` as the sanctioned split path.
