---
schemaVersion: 0.1.0
id: "0005"
title: "Treat plugin version as the cache key and keep dual manifests in lockstep"
status: proposed
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [packaging, versioning, apm, ci]
scope: org
reversibility: one-way-door
blastRadius: cross-team
relatesTo: ["0001", "0004"]
affects:
  - type: path
    pattern: plugins/*/.claude-plugin/plugin.json
  - type: path
    pattern: plugins/*/apm.yml
  - type: path
    pattern: plugins/plugin-forge/scripts/check-version-bump.sh
  - type: path
    pattern: plugins/plugin-forge/scripts/check-manifests.sh
provenance:
  authoredBy: agent-drafted
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0005: Treat plugin version as the cache key and keep dual manifests in lockstep

## Context

Every plugin carries two manifests: `.claude-plugin/plugin.json` for Claude Code
and GitHub Copilot CLI, and a sibling `apm.yml` for APM. This duplication is
deliberate — it is what keeps the plugin-native layout authoritative and avoids
an `.apm/` directory — but duplication invites drift.

Two failure modes make this more than a tidiness concern.

**Version is a cache key, not a label.** Claude Code caches plugin content
against `version`. Pushing commits without bumping it ships *nothing*: the fix
is merged, CI is green, and users continue running the old code. The failure is
silent and points away from itself — the natural conclusion is that the fix was
wrong, not that it was never delivered.

**APM does not read `plugin.json` dependencies.** Inter-plugin dependencies must
be declared separately in `apm.yml` as local-path deps. So the two files are not
merely redundant copies; each carries something the other does not, and neither
can be generated from the other. `description` is also intentionally divergent —
`apm.yml` uses a more concise variant tuned for CLI listings.

That leaves `name` and `version` as the fields that must be *strictly*
identical, and everything else as legitimately independent.

## Decision

We will keep `name` and `version` strictly identical between `plugin.json` and
`apm.yml`, and will treat a version bump as a required part of shipping any
change to plugin content. CI enforces both: `check-manifests.sh` for drift, and
`check-version-bump.sh` on pull requests for the bump itself.

Docs-only, test-only, and `CHANGELOG.md` edits are exempt. A deliberate skip
uses a `Skip-Version-Bump: <plugin> - <reason>` commit trailer, which the gate
echoes into the CI log so the exemption is visible rather than silent.

## Options considered

### Option A: Strict lockstep, CI-enforced, with an auditable escape hatch (chosen)

| Dimension | Assessment |
|---|---|
| Silent no-op ships | Prevented at PR time |
| Manifest drift | Caught by `check-manifests.sh` |
| Legitimate exemptions | Trailer, echoed into the log |
| Cost | Two files to touch; one more required CI gate |

### Option B: Generate `apm.yml` from `plugin.json`

**Pros:** Eliminates drift structurally rather than by checking.
**Cons:** The files are not projections of one another — `apm.yml` holds
dependencies `plugin.json` cannot express, and a deliberately different
`description`. Generation would have to preserve hand-authored fields through
regeneration, which is a merge problem dressed as a build step.

### Option C: Enforce the bump with no exemption

**Pros:** Simplest rule; nothing to argue about.
**Cons:** Forces meaningless version churn for typo fixes and test-only changes,
which trains contributors to bump reflexively — defeating the signal the version
is supposed to carry.

### Option D: Rely on review

**Cons:** This is what the "cache key" failure mode defeats. The symptom appears
after merge, to users, and does not look like a versioning problem.

## Trade-offs

- Two required CI gates on a repository whose contributions are frequently
  documentation. The exemption list is what keeps this tolerable, and it is a
  list that will need maintenance as new file categories appear.
- The `Skip-Version-Bump` trailer is honest but bypassable by anyone willing to
  write one. It is an audit trail, not an enforcement boundary.
- `one-way-door` is declared deliberately: once published versions exist in host
  caches, the versioning contract cannot be retroactively changed without
  stranding installs.

## Consequences

- **Easier:** a merged fix actually reaches users; drift is caught mechanically.
- **Harder:** every shipping change touches two manifests.
- **How we would know this was wrong:** `Skip-Version-Bump` trailers appear on
  changes that genuinely alter plugin behavior — meaning the exemption is being
  used to route around the gate rather than to document a real exception.
- **Revisit if:** a host stops using `version` as its cache key, or the two
  manifest formats converge upstream.

## Action items

1. [ ] Periodically audit `Skip-Version-Bump` trailers against shipped diffs.
