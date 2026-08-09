---
schemaVersion: 0.1.0
id: "0009"
title: "Publish the memory contract as memorykit with a copied release workflow"
status: proposed
date: 2026-08-09
deciders: []
tags: [packaging, release, pypi, memory, supply-chain, one-way-door]
scope: org
reversibility: one-way-door
blastRadius: team
relatesTo: ["0002", "0005", "0006", "0007", "0008"]
affects:
  - type: package
    pattern: memorykit
    note: >-
      The PyPI distribution name this record claims. First upload is
      irreversible; the name is unclaimed as of this record.
  - type: path
    pattern: plugins/memory/pyproject.toml
    note: Declares the distribution name, the zero-dependency set, and the entry points.
  - type: path
    pattern: plugins/memory/src/memorykit/**
    note: The packaged unit, moved here whole rather than split.
  - type: path
    pattern: plugins/memory/scripts/memory-provider.py
    note: >-
      Launcher shim preserving the path named by hooks.json; its bundled-first
      precedence is a decision, not an accident.
  - type: path
    pattern: plugins/memory/mcp/server.py
    note: Launcher shim preserving the path named by .mcp.json.
  - type: path
    pattern: .github/workflows/release-memorykit.yml
    note: >-
      The deliberate copy of release-indexkit.yml; its filename is load-bearing
      for the Trusted Publisher claim.
  - type: path
    pattern: docs/releasing.md
    note: Where the tag-prefix rule is generalized to distribution names.
provenance:
  authoredBy: agent
---

# ADR-0009: Publish the memory contract as memorykit with a copied release workflow

## Context

ADR-0006 accepted that "the memory contract/validator/MCP server" should ship as
an installable package, and ADR-0002 explained why *that* unit is the separable
one: it is pure standard library and useful without an agent host, while the
plugin around it — skills, commands, hooks — is host content that PyPI cannot
carry. ADR-0008 published `indexkit` and explicitly deferred one question to
whoever packaged memory next: copy its release workflow, or factor both onto a
reusable one.

What ADR-0006 did not fix, and what has to be fixed now, is where the packaging
boundary actually falls. The prose implies three things — a contract, a
validator, an MCP server — but the code is two files: a 344-line MCP server and a
2894-line provider script that contains the contract, the validator, the review
state machine, the local store, the provider adapters, session mining, and the
hook dispatcher. The MCP server shells out to the provider for *every* operation,
by design, so that the CLI and MCP surfaces cannot drift. So "the MCP server" is
not independently shippable, and "contract + validator" is not a clean cut
either: `validate` is separable, but `capture` — the operation the contract
exists to serve — depends on the review state machine, the append-only writer,
and the store lock.

Three decisions here are one-way doors or close to it. A PyPI name, once
uploaded, is permanent — ADR-0007 exists because we learned that on `indexkit`.
The public path of an entry point that hooks and MCP configs already name is
expensive to move. And the tag scheme is what a maintainer types at the moment of
an irreversible publish.

## Decision

We will publish the memory provider and MCP server as **`memorykit`**, a
zero-dependency, standard-library-only Python distribution built from
`plugins/memory/src/memorykit/`, released by a **copy** of the `indexkit` release
workflow under the tag prefix **`memorykit/v<version>`**.

Concretely:

1. **Name: `memorykit`.** Verified unclaimed on PyPI before choosing it
   (`memory`, `memkit`, `contextkit`, and `recallkit` are all taken, so
   plugin-name parity was never available). It extends the `indexkit` naming
   family established by ADR-0007, and needs no dash-to-underscore mapping
   between the distribution name and the import name.

2. **Boundary: both files, whole and unsplit — a deliberate superset of what
   ADR-0006 literally asked for.** The published unit is the provider *and* the
   MCP server, moved with `git mv`, not refactored. Splitting the provider to
   match ADR-0006's three-part phrasing would create an import graph inside a
   file whose single-file nature is currently a property — it is executed
   directly by `hooks.json` with `python3 <path>`, with no package context. The
   contract and validator are not extractable from `capture` without also
   extracting the state machine they enforce.

3. **Layout: `src/memorykit/`, with launcher shims left at both old paths.**
   `scripts/release_version.py` reads `<plugin>/src/<package>/__init__.py`, so
   the `src/` layout is required, not chosen. `scripts/memory-provider.py` and
   `mcp/server.py` remain as small Python launchers because `hooks/hooks.json`
   and `.mcp.json` name those exact paths and roughly 55 references across
   skills, commands, and docs depend on them.

4. **Launcher precedence: bundled source first, installed package second — the
   reverse of `bin/indexkit`.** `indexkit`'s launcher prefers an installed
   runtime because its bundled runtime may not be usable. Memory's bundled source
   always exists, and a globally installed `memorykit` at a different version
   would silently run provider code that does not match the plugin's own hooks,
   commands, and documentation. A test enforces the ordering.

5. **Tag prefix is the distribution name, not the plugin directory name.**
   `memorykit/v0.6.0`, not `memory/v0.6.0`. `release_version.py` already requires
   `tag.startswith(f"{package}/v")`; for `indexkit` the two names coincided, so
   this never surfaced. Still one tag per release — it releases the plugin and
   the package together, exactly as `indexkit/v…` does.

6. **The release workflow is copied, not shared.** This resolves ADR-0008 action
   item 4.

7. **The sdist ships no tests.** Verified empirically: five tests fail when run
   from an unpacked sdist because they assert on plugin-deployment facts
   (`hooks/hooks.json`, the sibling `indexkit` bootstrap) that a source
   distribution does not contain. Package invariants are enforced by
   `plugins/memory/tests/test_packaging.py` in the repository instead.

## Options considered

### Option A: Ship both files whole as `memorykit`, with a copied workflow (chosen)

| Dimension | Assessment |
|---|---|
| Fidelity to ADR-0006 | Superset. Ships everything named, plus the provider internals that the named parts cannot run without. |
| Purity constraint | Holds. Zero runtime dependencies, asserted by an AST walk over every import in the package. |
| Plugin breakage | None. Both entry-point paths survive as launchers; the existing suites pass unmodified in behaviour. |
| Cost | Two release workflows to keep in sync; a package whose surface is wider than its headline claim. |
| Reversibility | The name is permanent. The boundary and the layout are not. |

### Option B: Extract a narrow contract-and-validator core and leave the rest

**Pros:** matches ADR-0006's wording exactly; the published surface is small,
easy to document, and easy to keep stable.

**Cons:** it is not a real seam. `capture` — the operation that makes a contract
worth publishing — needs `_initial_state`, `_validate_transition`,
`_write_json_once`, and the store lock. Extracting them means either duplicating
the state machine or publishing it anyway under a different heading. It also
means the MCP server, which ADR-0006 explicitly names, could not ship, since
every one of its operations shells out to the provider. The choice was between
a package that does less than ADR-0006 promises and one that does more; more is
the honest one.

### Option C: Split the provider into modules first, then package the subset

**Pros:** a 2894-line file is genuinely large, and modules would make the
published surface legible.

**Cons:** the single-file property is load-bearing. `hooks.json` invokes it as
`python3 <path> hook <event>` with no package on `sys.path`; a module graph
requires either a package context at every call site or `sys.path` surgery in the
shim. The instruction to package it did not invite a refactor of it, and a
refactor concurrent with a move makes the diff unreviewable — the move is
already large enough that `git mv` fidelity is the main reviewability tool.
Deferred, not rejected: it can happen later, behind a stable published surface.

### Option D: Factor both release workflows onto one reusable workflow

**Pros:** one place to fix release hardening; ADR-0008 named it as a live option.

**Cons:** **PyPI does not support it.** A Trusted Publisher's OIDC claim names
the *calling* workflow, so a reusable workflow cannot be the registered
publisher (`pypi/warehouse#11096`). Adopting it would also mean re-registering
the already-live `indexkit` publisher — churning a working supply-chain
configuration for a refactor that cannot work. This is a technical constraint,
not a preference, and it is why item 4 resolves the way it does.

### Option E: Do nothing — leave memory plugin-only

**Pros:** zero new surface, zero new one-way doors, no second release pipeline.

**Cons:** leaves ADR-0006 item 3 open indefinitely and keeps the one component
that provably does not need an agent host locked behind one. ADR-0002 already
rejected the reverse framing (extracting memory to its own repository); staying
unpublished is the same isolation with none of the benefit.

## Trade-offs

- **Two release workflows drift.** The copy has to be updated in lockstep with
  `release-indexkit.yml` forever. Both files, and `docs/releasing.md`, say so.
- **The published surface is wider than the headline.** `memorykit` also carries
  provider adapters, hook dispatch, and Copilot session mining. All degrade
  rather than fail with no host — the default provider is `none` — but they are
  in the package, and a narrower public claim would be dishonest.
- **The name is permanent.** If the boundary is later judged wrong, the name
  still cannot be recycled.
- **Two launchers now exist that could go stale.** Mitigated by tests that
  execute them, not merely check that they exist.
- **`memory` and `memorykit` differ**, so a reader must know the plugin/package
  distinction to find the right tag. `docs/releasing.md` carries the table.

## Consequences

- **Easier:** using the memory contract, validator, and MCP server from any host
  — `pip install memorykit` and one environment variable. No Python dependencies
  means no resolver conflicts and no build toolchain. It is not dependency-free
  in the broader sense: `validate` and `capture` require `git` on `PATH` for
  `git check-ref-format`, which is documented rather than removed (reimplementing
  Git's refname rules would be unreviewed, and skipping the check when `git` is
  absent would weaken provenance silently).
- **Harder:** every release-hardening fix now lands in two workflow files.
  Changing the provider's internal structure now has an external audience.
- **How we would know this was wrong:** the boundary is wrong if, within two
  releases, we ship a change to `memorykit` that exists only to serve the plugin
  and is meaningless to a package-only consumer, or the reverse — that is the
  signature of a seam in the wrong place. The copied workflow is wrong if the two
  release files diverge in *hardening* (not merely in names) in any single
  release. The name is wrong only if `pip install memorykit` is not what someone
  reaching for this reaches for; there is no metric for that, and no remedy.
- **Revisit if:** PyPI ever supports reusable workflows as Trusted Publishers
  (then merge them, and re-register both); or the provider is split into modules
  (then re-examine whether the published surface should narrow with it); or a
  third plugin needs publishing, at which point two copies become three and the
  duplication argument should be re-run rather than assumed.

## Action items

1. [x] Move both files into `plugins/memory/src/memorykit/` with `git mv`,
   preserving history, and fix the two layout-dependent path computations.
2. [x] Add `pyproject.toml` with no runtime dependencies, `requires-python`
   `>=3.10`, and the `memorykit` / `memorykit-mcp` console scripts.
3. [x] Leave Python launcher shims at `scripts/memory-provider.py` and
   `mcp/server.py`, preferring the bundled source.
4. [x] Copy `release-indexkit.yml` to `release-memorykit.yml`, retaining every
   hardening: `needs:`-gated publish, tag-only trigger, version guard, artifact
   assertion, `twine check --strict`, explicit upload globs, and attestations.
5. [x] Add `tests/test_packaging.py` asserting stdlib purity, zero dependencies,
   entry points, version agreement, and launcher precedence.
6. [x] Generalize the tag-prefix rule in `docs/releasing.md` to distribution
   names and add the `memorykit` publishing section.
7. [ ] **Maintainer, at publish time:** create the PyPI pending publisher for
   `memorykit` (owner `mbeacom`, repository `context-kit`, workflow
   `release-memorykit.yml`, environment `pypi`), then push `memorykit/v0.6.0`.
   Deliberately not done here: the first upload claims the name permanently.
8. [ ] Re-run the copy-versus-reusable decision when a third publishable plugin
   appears, or if `pypi/warehouse#11096` is resolved.
