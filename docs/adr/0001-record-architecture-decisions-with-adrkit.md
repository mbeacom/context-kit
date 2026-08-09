---
schemaVersion: 0.1.0
id: "0001"
title: "Record architecture decisions with adrkit"
status: accepted
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [governance, decision-memory, dogfooding]
scope: org
reversibility: two-way-door
blastRadius: team
relatesTo: []
affects:
  - type: path
    pattern: docs/adr/**
    note: The corpus itself.
  - type: path
    pattern: .github/workflows/validate.yml
    note: Where corpus linting is enforced.
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0001: Record architecture decisions with adrkit

## Context

`context-kit` is a catalog of context-engineering plugins, and its own design
rules live in three always-loaded instruction files — `AGENTS.md`, `CLAUDE.md`,
and `.github/copilot-instructions.md`. Those files state rules well ("keep
`marketplace.json` hand-authored") but they are lossy in three specific ways:

1. **They record the rule, not the reasoning.** `AGENTS.md` says not to run
   `apm pack`; the *why* survives only in a parenthetical about a dropped
   `category` field and an upstream PR number.
2. **Rejected options vanish.** Nothing in the repo records what was considered
   and ruled out, so an agent — or a contributor — re-proposes settled paths.
   This is not hypothetical: the memory-split question in this session was
   re-litigated from scratch because no prior record existed.
3. **They are unlocatable.** The rules are global prose. Nothing can answer
   "which decisions govern `plugins/memory/`?" without a human reading all three
   files and filtering by memory.

The instruction files are also a scarce resource. They are loaded on every turn,
so they are the wrong place to put decision *rationale* that is only needed when
a specific area is touched. The repo already knows this — `context-budget` is a
whole skill about placing guidance at the right scope. Decision rationale
belongs at path scope, retrieved on demand, which is exactly the placement the
instruction files cannot provide.

## Decision

We will record architecture decisions as machine-readable ADRs in `docs/adr/`,
managed by [adrkit](https://github.com/mbeacom/adrkit), and we will populate
`affects` on every record so decisions are locatable by path.

The instruction files keep the *rules*. The ADR corpus holds the *reasoning,
the rejected options, and the revisit conditions*.

## Options considered

### Option A: adrkit ADRs with `affects` (chosen)

| Dimension | Assessment |
|---|---|
| Records rationale | Yes — structured Context/Options/Trade-offs sections |
| Preserves rejected options | Yes — `status: rejected` and `superseded` stay queryable |
| Locatable by path | Yes — `affects` + `adr explain <path>` |
| CI-enforceable | Yes — `adr lint` |
| Agent-legible | Yes — read-only offline MCP server |
| Cost | A new dev dependency (Node/npx); one more corpus to maintain |

### Option B: Keep expanding the instruction files

**Pros:** Zero new tooling. Already loaded, so guaranteed to be seen.
**Cons:** Directly fights the catalog's own discovery budget — those files are
always-on context. Cannot express path scope, so every decision's rationale is
paid for on every turn regardless of relevance. No way to represent a *rejected*
option other than prose an agent may read as current guidance.

### Option C: Plain MADR markdown, no tooling

**Pros:** No dependency; ADRs are just files.
**Cons:** Gives up the property that motivated this. Without typed `affects`
there is no `adr explain`, no CI conformance, and no agent query surface —
it records decisions without making them *do* anything. The repo would have
documentation, not decision memory.

### Option D: Do nothing

**Pros:** No cost.
**Cons:** Accepts the re-litigation demonstrated in this session as permanent.

## Trade-offs

What this costs, stated plainly:

- **A Node toolchain dependency in a Python/Markdown repo.** `context-kit`'s
  runtime is Python stdlib and shell by design. adrkit is Node 22+. We accept
  this only because it is a *contributor-side* dependency: no shipped plugin
  imports it, and no user installing a plugin needs it.
- **adrkit is early.** Its own README states no external adopters and that
  rung-3 validation is unmet. We are an early adopter and should expect
  breaking changes across 0.x.
- **License asymmetry.** adrkit is Apache-2.0; `context-kit` is MIT. We may
  invoke it but may never vendor its code.
- **A second corpus to keep honest.** An ADR corpus that rots is worse than
  none, because it looks authoritative.

## Consequences

- **Easier:** answering "why is it this way?" for any path; onboarding agents
  to settled constraints; refusing re-litigation with a citation.
- **Harder:** decisions now have a write cost. Small reversible choices should
  *not* become ADRs — see the threshold below.
- **How we would know this was wrong:** if, six months on, `adr explain` on a
  frequently-edited path returns nothing useful, the corpus is not tracking real
  decisions and is pure overhead. Concretely: if fewer than 5 records exist by
  2027-02-08, or if `adr lint` is disabled in CI to unblock a merge, revisit.
- **Revisit if:** adrkit is abandoned upstream, or a 0.x break costs more than
  one maintenance session to absorb. Exit is cheap — the records are plain
  Markdown with YAML frontmatter and survive the tool's removal.

## Threshold

Write an ADR when a choice is **hard to reverse, contested, or governs a path**.
Do not write one for naming, formatting, or any choice a future contributor can
flip in a single commit without coordination.

## Action items

1. [x] Scaffold `docs/adr/` and author the founding records.
2. [ ] Add `adr lint` to CI as a non-blocking check first, then enforce.
3. [ ] Document the corpus in `docs/contributing.md`.
