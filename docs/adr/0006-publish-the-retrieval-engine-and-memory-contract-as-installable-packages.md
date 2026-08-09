---
schemaVersion: 0.1.0
id: "0006"
title: "Publish the retrieval engine and memory contract as installable packages"
status: accepted
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [packaging, distribution, local-rag, memory, pypi]
scope: org
reversibility: one-way-door
blastRadius: cross-team
relatesTo: ["0002", "0005", "0008", "0009"]
affects:
  - type: path
    pattern: plugins/indexkit/**
    note: Renamed from local-rag by ADR-0007; prose below predates the rename.
  - type: path
    pattern: plugins/memory/**
  - type: package
    pattern: indexkit
    note: The PyPI name claimed by first publish. Name settled by ADR-0007.
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0006: Publish the retrieval engine and memory contract as installable packages

## Context

ADR-0002 asked whether `memory` should move to its own repository and answered
no. That record conflated two questions, and its reasoning has been corrected:
*repository location* and *independent consumability* are separate decisions.
This record resolves the second.

Today neither component is consumable outside a plugin host, and the two are
blocked for different reasons.

**`local-rag` is nearly there and simply unpublished.** It already has a real
`pyproject.toml` (hatchling, pinned `turbovec>=0.5` and `httpx>=0.27`,
`requires-python >=3.10`), a `uv.lock`, a console entry point
(`local-rag = "local_rag.cli:main"`), and a complete human CLI: `index`,
`query`, `status`, `list`, `remove`, with `--json`, `--k`, and `--allowlist`.
The name is unclaimed on PyPI. What blocks a `pip install` user is not the code
but the delivery path: `bin/rag` is a shell shim that requires a venv
bootstrapped by a `SessionStart` hook, and the default index location is
`~/.claude/plugins/data/local-rag` — a host-specific path baked in as the
fallback for a tool that is otherwise host-neutral.

**`memory` has no packaging at all**, though it is pure standard library
(`from __future__ import annotations` is its only non-stdlib-looking import), so
packaging it is mechanical rather than architectural.

The cost of leaving this is not hypothetical. It makes claims about these
components unfalsifiable. ADR-0002's original revisit trigger — "an outside
consumer adopts the contract" — could never fire, because nothing was published
for anyone to adopt. Publishing is what converts assertions about external value
into observable evidence.

Publishing also *replaces* the motivation for splitting the repository. Everything
a split promises — an installable artifact, its own version, users who never
clone the catalog — is delivered by publishing a package, without the cross-repo
coordination cost that ADR-0002 measured.

## Decision

We will publish `local-rag` to PyPI as a standalone, host-neutral package, and
package the `memory` record contract, validator, and MCP server as a second
installable artifact. Both continue to live in this repository (ADR-0002), and
the plugins become thin wrappers over the published packages rather than the
only way to obtain them.

A published package must work under a plain `pip install` with **no plugin host,
no bootstrap hook, and no Claude-specific default path**. Host integration
becomes an optional layer over a working CLI, not a prerequisite for one.

Because a first publish permanently claims a name, the name is settled *before*
the first release, not after (see Action items).

## Options considered

### Option A: Publish from the monorepo; plugins wrap the packages (chosen)

| Dimension | Assessment |
|---|---|
| Independently installable | Yes — `pip install` / `uv tool install` |
| Repo coordination cost | None; same-commit refactors still work |
| Host-neutral defaults | Required by this decision |
| Claims about adoption | Become falsifiable |
| Cost | A release pipeline, and packaging discipline forever after |

### Option B: Status quo — plugin-only distribution

**Pros:** No release pipeline, no packaging discipline, no name to defend.
**Cons:** Keeps both components agent-only and keeps every claim about their
standalone value untestable. Also wastes work already done: `local-rag` carries
a full package definition and an unclaimed name that no one can install.

### Option C: Split into separate repositories to force independence

**Pros:** Independence is structural rather than a matter of discipline.
**Cons:** ADR-0002 measured this: it exports two dependencies, imports no
consumers, and binds the extracted component to a *faster-churning* dependency
across a repo boundary. It buys distribution — which Option A also buys — at the
price of coordination Option A does not pay.

### Option D: Publish `local-rag` only, defer `memory`

**Pros:** Smallest step; `local-rag` is closest to ready and has the clearest
standalone story (a hybrid semantic/lexical index with a working CLI).
**Cons:** Leaves ADR-0002's corrected trigger only half-observable. Worth
considering as *sequencing* rather than as a terminal state — and in practice
this is how it will ship, since `local-rag` is ready first.

## Trade-offs

- **A published name is close to permanent.** PyPI names are sticky and
  unpublishing strands installs. This is why `reversibility: one-way-door` is
  declared, and why naming must be resolved before the first release rather
  than discovered after it.
- **A release pipeline is ongoing cost**, and this repository already carries
  several CI gates. Publishing adds versioning duties beyond the plugin cache-key
  rules in ADR-0005 — the package version and the plugin version are now two
  artifacts that can drift.
- **Host-neutral defaults require changing existing behavior.** The
  `~/.claude/plugins/data/` fallback and the bootstrap-dependent shim exist for
  good plugin reasons; making the package work standalone means those become the
  *plugin's* concern rather than the library's.
- **Public packages attract support load** — issues, questions, and
  compatibility requests from users who never touch the catalog. That is the
  point, but it is not free.

## Consequences

- **Easier:** anyone can install and evaluate the tools; claims about their
  standalone value become measurable; the plugin stops being the only entry
  point.
- **Harder:** two versioned artifacts per component; a name that cannot be
  casually changed; a support surface.
- **How we would know this was wrong:** twelve months after first release, the
  packages show negligible installs outside our own CI *and* the packaging
  discipline has measurably slowed catalog work. That is falsifiable, unlike the
  trigger it replaces.
- **Revisit if:** the packaging burden begins driving design decisions inside
  the plugins, rather than the reverse.

## Action items

1. [x] **Settle the name before first publish** — resolved by ADR-0007:
   renamed to `indexkit`, unifying the package, console script, CLI `prog`, and
   launcher on one name before the PyPI name was claimed.
2. [x] Make the CLI work with no plugin host: host-neutral default data dir
   (`${XDG_DATA_HOME:-~/.local/share}/indexkit`), and a launcher that degrades
   to an installed console script or an importable module.
3. [x] Add a `pyproject.toml` for the memory contract/validator/MCP server.
   Resolved by ADR-0009 as the `memorykit` distribution, with one correction to
   this record: the three named parts are not a shippable unit on their own. The
   MCP server shells out to the provider for every operation by design, and
   `capture` cannot be separated from the review state machine, so the package
   ships the provider and the MCP server whole rather than a narrow core. That
   is a superset of what this item asked for, chosen over a narrower cut that
   would have had to duplicate the state machine or drop the MCP server.
4. [x] Add a release workflow; keep package and plugin versions reconciled with
   ADR-0005. See ADR-0008 for `indexkit` and ADR-0009 for `memorykit`.

`indexkit` 0.6.1 was published to PyPI on 2026-08-09, so this record's central
claim is now testable rather than asserted: `pip install indexkit` works with no
plugin host. The revisit trigger — negligible installs outside our own CI at
twelve months, *and* packaging discipline measurably slowing catalog work —
becomes observable from that date.
