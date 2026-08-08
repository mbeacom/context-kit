---
schemaVersion: 0.1.0
id: "0004"
title: "Hand-author the marketplace catalog instead of generating it"
status: accepted
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [packaging, apm, catalog]
scope: component
reversibility: two-way-door
blastRadius: team
relatesTo: ["0001"]
affects:
  - type: path
    pattern: .claude-plugin/marketplace.json
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0004: Hand-author the marketplace catalog instead of generating it

## Context

`.claude-plugin/marketplace.json` is the catalog read by Claude Code, GitHub
Copilot CLI, and APM alike. APM ships `apm pack`, which generates this file from
the per-plugin manifests — the obvious way to keep it in sync and the way a
contributor will reach for by default.

`apm pack` output drops the per-plugin `category` field. Category is what gives
the catalog navigable structure across 13 plugins; losing it silently degrades
discovery for every host, and the loss is invisible in review because the
generated file otherwise looks correct.

This is fixed upstream in microsoft/apm#2189, merged but unreleased as of
2026-07. So the constraint is real but explicitly temporary, which is exactly
the kind of fact that rots into folklore if only recorded as an instruction-file
parenthetical.

There is a second, more durable reason. The catalog is not a pure projection of
the manifests: it lists **only shipped plugins**. A plugin can exist in
`plugins/` with a complete manifest while deliberately staying out of the
catalog until it is ready. Generation would publish stubs the moment they parse.

## Decision

We will hand-author `.claude-plugin/marketplace.json`, and will not run
`apm pack` to regenerate it. A plugin gains a catalog entry only when it is
ready to ship.

## Options considered

### Option A: Hand-author (chosen)

| Dimension | Assessment |
|---|---|
| `category` preserved | Yes |
| Unready plugins stay unlisted | Yes — listing is a deliberate act |
| Drift risk | Real; mitigated by `check-manifests.sh` |
| Cost | One manual edit per shipped plugin |

### Option B: Generate with `apm pack`

**Pros:** No drift between manifests and catalog; one less manual step.
**Cons:** Drops `category`. Also makes "in `plugins/`" equivalent to "shipped",
removing the staging property — a half-built plugin becomes installable as soon
as its manifest is valid.

### Option C: Generate, then patch `category` back in

**Pros:** Keeps generation while restoring the lost field.
**Cons:** A post-processing step over a generator's output is strictly more
machinery than the hand edit it replaces, and it still cannot express the
ship/no-ship distinction.

### Option D: Do nothing (no stated rule)

**Cons:** The status quo before this record — a contributor runs `apm pack`
helpfully, `category` disappears, and review does not catch it.

## Trade-offs

- Drift between `marketplace.json` and per-plugin manifests is now possible.
  `check-manifests.sh` covers `plugin.json` ⇆ `apm.yml`, so catalog drift
  specifically rests on review discipline.
- The rule will outlive its cause. When apm#2189 ships, Option A's primary
  justification weakens to the staging argument alone.

## Consequences

- **Easier:** categories survive; unready plugins cannot be installed
  half-built.
- **Harder:** shipping a plugin is a two-file act.
- **How we would know this was wrong:** a catalog entry drifts from its manifest
  in a way `check-manifests.sh` cannot see, and a user installs something
  mislabeled.
- **Revisit if:** apm#2189 ships in a released version — at which point
  re-verify `apm pack` output preserves `category` *and* decide whether the
  staging property is worth keeping generation out.

## Action items

1. [ ] On the next APM release, re-verify `apm pack` output against this record.
