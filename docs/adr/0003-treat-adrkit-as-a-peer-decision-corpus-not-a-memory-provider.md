---
schemaVersion: 0.1.0
id: "0003"
title: "Treat adrkit as a peer decision corpus, not a memory provider"
status: accepted
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [memory, adrkit, retrieval, integration, boundaries]
scope: org
reversibility: two-way-door
blastRadius: cross-team
relatesTo: ["0001", "0002"]
affects:
  - type: path
    pattern: plugins/memory/**
    note: Owns type:decision records; the boundary this ADR draws.
  - type: path
    pattern: plugins/retrieval-core/**
    note: Routes the decision-memory modality.
  - type: path
    pattern: plugins/verify/**
    note: change-impact gains governance blast radius.
  - type: path
    pattern: plugins/plan-execute/**
  - type: path
    pattern: plugins/deep-review/**
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0003: Treat adrkit as a peer decision corpus, not a memory provider

## Context

ADR-0001 adopts adrkit for this repository's own decisions. That immediately
raises a second, sharper question: what relationship should the *shipped
plugins* have with adrkit?

The tempting answer is that adrkit is a memory provider. `plugins/memory`
already has a provider abstraction with three registered backends (local-only,
`rag`, MemPalace), a formal 12-criterion qualification policy, and a decision
table. adrkit stores durable, provenance-carrying, supersession-aware records in
git. It looks like it slots straight in.

Running adrkit honestly through `provider-qualification.md` shows it does not.
It passes criteria 1, 3, and 6–12 comfortably: versioned npm releases at 0.3.0,
git-scoped isolation, explicitly no network and no credentials, export/delete
via plain files, a test suite with CI, and an MCP server that is separately
installable and not a prerequisite for CLI use.

It fails **criterion 4 (provenance and immutable evidence round-tripping)** —
but not for the usual reason. It is not lossy. It simply is not a `memory-v1`
store at all. It is a different schema answering a different question. Making it
a provider would mean either coercing ADRs into `memory-v1` frontmatter or
coercing memory records into the ADR schema. Both destroy the thing that makes
the target useful.

There is also a live collision to resolve regardless. `memory` already has
`type: decision`. Both systems are git-adjacent, both carry provenance, both
model supersession. Without a stated boundary the project ships **two decision
stores** and no rule for which one an agent should write to — the worst outcome,
because retrieval silently returns half the answer.

Finally, adrkit's real shape argues against the provider framing. Its MCP server
is read-only, offline, no-LLM, `readOnlyHint: true`, `openWorldHint: false`. It
is a *retrieval surface*. `context-kit`'s architecture is already organized
around retrieval modalities selected by `retrieval-core`. adrkit fits that
existing abstraction exactly, and fits the provider abstraction not at all.

## Decision

We will treat adrkit as a **peer decision corpus and a distinct retrieval
modality**, integrated by invocation and never as a `memory` provider.

We draw the boundary as:

| | `context-kit` memory | adrkit |
|---|---|---|
| Records | Agent-observed, evidence-bound | Team-ratified, human-reviewed in PR |
| Scope | Session-derived, project-scoped | Repository governance |
| Lifecycle | Capture → review → accept | Propose → ratify → supersede |
| Enforcement | Recall-time | CI (`adr lint`, `adr check`) |
| Locatability | Cue anchors, semantic recall | `affects` path patterns |

A `type: decision` memory record is an **observation that a decision was made**.
An ADR is **the decision, ratified**. The relationship is a promotion path, not
an overlap: `/capture-memory` on a `type: decision` record may suggest
`adr new`. It must never write one, because ratification is a human act —
a property adrkit enforces via `provenance.ratifiedBy`, as this corpus
discovered when the first agent-drafted record was refused at `accepted`.

Every integration is **optional and degrades to `unavailable`**. No shipped
plugin may take adrkit as a hard dependency.

## Options considered

### Option A: Peer corpus + retrieval modality, optional everywhere (chosen)

| Dimension | Assessment |
|---|---|
| Schema integrity | Both corpora keep their own schema |
| Fits existing architecture | Yes — modality routing already exists |
| Coupling | Loose; absent tool → `unavailable`, never a hard dep |
| Boundary clarity | Explicit table; promotion path, no overlap |
| Cost | Two corpora; users must learn which is which |

### Option B: Register adrkit as a `memory` provider

**Pros:** Reuses the existing provider abstraction and its qualification
machinery; one configuration surface for users.
**Cons:** Fails criterion 4 as shown. Requires lossy coercion in one direction
or the other. Worse, it inverts the trust model: `memory` providers are
*indexes over* records that memory owns, and memory can rebuild any provider
from its own artifacts. adrkit's corpus is owned by the repository and its
humans; memory must not be able to rebuild, mutate, or garbage-collect it.

### Option C: Absorb ADRs into `memory` as a record subtype

**Pros:** Single store; one retrieval path; no boundary to teach.
**Cons:** Discards CI enforcement and `affects` path resolution — the two
properties that make ADRs actionable. Also puts ratified team governance behind
an agent-writable capture loop, which is precisely backwards.

### Option D: Do nothing; keep adrkit purely for this repo's own docs

**Pros:** Zero shipped-surface risk while adrkit is early.
**Cons:** Forfeits the integrations with the clearest fit — notably
`change-impact`, where "which decisions govern the files I am about to change?"
is a question the plugin currently cannot answer at all. Leaves the
`type: decision` collision unresolved and undocumented.

## Trade-offs

- **Two corpora is a real cost.** Users and agents must learn the boundary. We
  mitigate with the table above and a routing rule, but the mitigation is
  documentation, which decays.
- **We are integrating with an early tool.** adrkit states it has no external
  adopters and unmet rung-3 validation. Optional-with-`unavailable` bounds the
  blast radius but does not eliminate churn cost.
- **Apache-2.0 vs MIT.** We may invoke adrkit but may never vendor its code.
  This constrains us to process/MCP boundaries — consistent with how the catalog
  treats every other external CLI, but it does close off tighter integration.
- **The promotion path is manual by design.** That is friction, and friction
  means some decisions will be captured as memory and never promoted.

## Consequences

- **Easier:** `change-impact` can report governance blast radius, not just
  structural; `plan-execute` can check a plan against governing decisions;
  `deep-review` gains a conformance lens; agents stop re-proposing rejected
  paths.
- **Harder:** two corpora to keep honest; contributors must know which to write
  to.
- **How we would know this was wrong:** if in practice `type: decision` memory
  records and ADRs contain substantially the same content, the boundary is
  fictional and one store should absorb the other. Check at the 10th ADR.
  Equally: if no integration beyond this repo's own dogfooding ships within two
  releases, Option D was the right call and we should retreat to it.
- **Revisit if:** adrkit reaches 1.0 with a stable schema, or a `memory`
  provider genuinely needs governance semantics.

## Action items

1. [ ] Record adrkit in `provider-qualification.md` as "not a provider — peer
   corpus", so the question is settled rather than re-asked.
2. [ ] Add `adr explain` as an optional `change-impact` catalog entry.
3. [ ] Document the decision-memory modality in `retrieval-core`.
4. [ ] Define the `type: decision` → `adr new` promotion suggestion.
