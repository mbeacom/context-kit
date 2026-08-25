---
schemaVersion: 0.1.0
id: "0010"
title: "Split adrkit integration between a context-kit bridge and an adrkit-hosted tool plugin"
status: accepted
date: 2026-08-15
deciders: ["@mbeacom"]
tags: [adrkit, governance, integration, boundaries, discovery-budget]
scope: org
reversibility: two-way-door
blastRadius: cross-team
relatesTo: ["0001", "0003"]
affects:
  - type: path
    pattern: plugins/adr-bridge/**
    note: The bridge this ADR creates; its scope boundary is the decision.
  - type: path
    pattern: plugins/deep-review/skills/deep-review/references/lens-charters.md
    note: Hosts the conformance charter ADR-0003 anticipated.
  - type: path
    pattern: plugins/verify/**
    note: Owns the enforced read-only governance operations the bridge calls.
  - type: path
    pattern: plugins/retrieval-core/**
    note: Routes generic decision memory to adrkit or verify and the memory-promotion and semantic-index joins to adr-bridge.
  - type: path
    pattern: plugins/plugin-forge/quality/**
    note: Encodes the decision-memory route and govern-then-change composition.
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0010: Split adrkit integration between a context-kit bridge and an adrkit-hosted tool plugin

## Context

ADR-0003 settled *what relationship* the shipped plugins have with adrkit: a peer
decision corpus and a distinct retrieval modality, integrated by invocation,
never a `memory` provider. It did not settle **where the integration code
lives**, because at the time there was only one candidate location.

Two facts have changed, and together they make the question a real decision
rather than a default.

**adrkit now ships its own agent-integration surface.** It publishes
`@adrkit/mcp`, `@adrkit/spec-kit`, and — since
[adrkit#157](https://github.com/mbeacom/adrkit/pull/157) — a portable agent
plugin for GitHub Copilot CLI, Claude Code, opencode, and APM. That plugin owns
the `decision-memory` skill, `decision-checker` agent, and `/adr-context`,
`/adr-check`, `/adr-draft`, and `/adr-queue` commands. A "how to use adrkit"
skill or generic plan-check command in this catalog would therefore be a second,
competing copy of behavior adrkit already maintains — and would track the wrong
release cycle. adrkit shipped 0.4.0 → 0.9.0 in about a month. This repository
demonstrated the failure mode directly: it documented `@adr` markers (a 0.5.0
feature) while instructing operators to install 0.4.0.

**The catalog's discovery budget is effectively exhausted.** Aggregate skill and
agent `description` text sits at 4093 of 4096 characters. Every skill and every
agent is charged against that budget on every turn; commands, reference files,
and scripts are not. A new plugin carrying a skill would have to evict
description text from existing components to pay for itself — that is, degrade
routing for shipped capabilities to fund a new one.

There is also a plain scoping fact. The useful downstream integrations are
**joins**: promote a `type: decision` memory record toward a ratifiable ADR, and
index the corpus so decisions are findable when no path is known. Each names a
plugin — `memory` or `indexkit` — that adrkit has no reason to know exists.
Conversely the generic context/check/draft/queue loop, CLI flags, schema, and
ratification rules are adrkit's own and change on its schedule.

## Decision

We will **split the integration by ownership of change**, and place each half
where its churn originates.

- **`context-kit` owns the bridge.** A new `adr-bridge` plugin holds only what
  references *this catalog's* plugins: `/promote-decision-to-adr`,
  `/index-decisions`, plus the `deep-review` `conformance` charter and the
  bridge-specific decision-memory compositions in `retrieval-core`.
- **adrkit owns the generic agent workflow and tool usage.** Its portable plugin
  owns context, plan checking, drafting, and queue review. Its CLI and MCP
  surfaces own flags, schema, and ratification rules, versioned with the tool
  they document.

`adr-bridge` ships **commands only** — no skill, no agent — so it costs zero
discovery budget. This is a fit, not only a workaround: governance is a
deliberate act, and a user-invoked command is the honest surface for one.

`verify` is the bridge's only dependency, for its enforced read-only runner.
`memory` and `indexkit` stay optional and are reported as `unreached` when
absent, per ADR-0003.

## Options considered

### Option A: Split by ownership of change — bridge here, tool usage in adrkit (chosen)

| Dimension | Assessment |
|---|---|
| Version skew | Each half tracks the repo whose releases change it |
| Duplication | None; adrkit's own agent plugin, MCP, and Spec Kit surfaces stay authoritative |
| Discovery budget | Zero cost — commands only |
| Completes ADR-0003 | Yes: action item 4 and both unbuilt consequences |
| Cost | Two repositories to coordinate and two plugins to install for the full composition |

### Option B: One full adrkit plugin in `context-kit`, including a tool-usage skill

**Pros:** Single install, single place to look, no cross-repo coordination.
**Cons:** Requires evicting existing description text to fund the skill, so
shipped routing degrades to pay for it. Duplicates adrkit's portable agent
plugin, Spec Kit adapter, and MCP server, and the copy rots on adrkit's cadence
while living in our release cycle — the 0.4.0/`@adr` skew is that failure
already observed once.

### Option C: Put everything in adrkit's repository

**Pros:** One owner; guaranteed version alignment with the CLI.
**Cons:** adrkit would have to model `memory-v1` records and `indexkit` to
express the joins, taking a dependency on a catalog it should not know about,
and inverting the direction of knowledge — the bridge is only meaningful to
someone who already has these plugins installed.

### Option D: Do nothing; keep the `verify` runner's two governance operations

**Pros:** Zero new surface while adrkit is pre-1.0.
**Cons:** Leaves ADR-0003 action item 4 and both named consequences unbuilt, and
leaves the corpus reachable only by path — so *"have we decided anything about
X?"* stays unanswerable. ADR-0003 named this outcome as the signal that Option D
had been right; choosing it now would be choosing not to test that.

## Trade-offs

- **The complete workflow takes two installs.** adrkit's plugin supplies ambient
  decision memory and the generic context/check/draft/queue loop; `adr-bridge`
  supplies only the context-kit-specific joins.
- **Commands are not auto-discovered.** A skill would let a model route to this
  capability unprompted; commands must be invoked. We accept weaker discovery for
  zero budget cost, and mitigate with `retrieval-core`, which routes generic
  decision memory to adrkit or `verify` and the bridge-specific joins here.
- **Two repositories can drift.** The bridge names adrkit commands and response
  buckets; a breaking 0.x change can break the handoff without breaking its
  manifest, and nothing here fails loudly when that happens.
- **A fifteenth plugin is more catalog to keep honest**, and its value is
  conditional on a corpus existing at all.

## Consequences

- **Easier:** promoting an observed decision into ratifiable governance; finding
  decisions by meaning; reviewing an artifact for conformance with a citation
  rather than an opinion; using adrkit's generic plan checking without a
  downstream copy.
- **Harder:** contributors must know which half owns a given change, and the
  bridge's instructions must be re-read against adrkit's changelog on each minor.
- **How we would know this was wrong:** if within two releases the bridge's
  commands are never invoked, the split was overhead and Option D was right.
  Equally, if the bridge accumulates tool-usage instruction — flag lists, schema
  field tables, ratification mechanics — the boundary is not holding and Option B
  or C should absorb it. Concretely: if `adr-bridge` commands grow to restate
  more than the argv they invoke, revisit.
- **Revisit if:** adrkit reaches 1.0 with a stable schema, the two-install
  workflow causes users to miss the bridge, or a breaking 0.x change costs more
  than one maintenance session to absorb.

## Action items

1. [x] Create `adr-bridge` with the two context-kit-specific bridging commands,
   commands-only.
2. [x] Add the `conformance` lens charter to `deep-review` (ADR-0003 consequence).
3. [x] Encode generic `decision-memory` routing, the bridge-specific joins, and
   the `govern-then-change` composition in the retrieval contracts.
4. [x] Update the adrkit pin from 0.4.0 to the current release, which the `@adr`
   marker documentation already assumed.
5. [x] adrkit shipped its portable agent plugin in
   [adrkit#157](https://github.com/mbeacom/adrkit/pull/157).
6. [x] Remove `/check-plan-against-decisions` after the upstream `/adr-check`
   command landed, so the ownership boundary is real rather than aspirational.
7. [x] Ratify this record as `@mbeacom`.
