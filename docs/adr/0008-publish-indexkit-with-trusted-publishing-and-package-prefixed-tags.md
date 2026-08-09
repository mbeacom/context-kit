---
schemaVersion: 0.1.0
id: "0008"
title: "Publish indexkit with trusted publishing and package-prefixed tags"
status: proposed
date: 2026-08-09
deciders: []
tags: [packaging, release, ci, pypi, supply-chain, indexkit]
scope: org
reversibility: one-way-door
blastRadius: team
relatesTo: ["0005", "0006", "0007"]
affects:
  - type: path
    pattern: .github/workflows/release-indexkit.yml
    note: The pipeline this record governs; its filename is load-bearing.
  - type: path
    pattern: scripts/release_version.py
    note: The pre-publish guard that enforces the tag/version contract.
  - type: path
    pattern: tests/release/**
  - type: path
    pattern: plugins/indexkit/**
    note: The versioned surfaces the guard reconciles.
  - type: package
    pattern: indexkit
provenance:
  authoredBy: agent-drafted
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0008: Publish indexkit with trusted publishing and package-prefixed tags

## Context

ADR-0006 decided to publish `indexkit` to PyPI and left "add a release workflow"
as an action item. ADR-0007 settled the name. What remains is the mechanism, and
the mechanism carries three choices that are awkward to change once real
releases exist.

**A publish is not reversible.** A file uploaded to PyPI cannot be replaced —
only yanked — and the version number is consumed permanently. So the interesting
design question is not "how do we upload" but "what must be true before an
upload is allowed to happen at all."

**The credential is a standing risk.** A PyPI API token in repository secrets is
a long-lived bearer credential for a package this repository does not yet own.
Anything that can run a workflow, or read secrets through one, can publish. The
window is unbounded because the token does not expire on its own.

**A bare version tag is ambiguous in this tree.** This repository ships 14
plugins from one commit history, and ADR-0006 already commits to a second
publishable artifact (`memory`). A tag `v0.6.0` does not say what is at 0.6.0,
and it forces every publishable component onto one shared version line — which
would mean bumping `indexkit` to release `memory`. `docs/releasing.md` already
resolved this for plugin releases with `<plugin-name>/v<version>`, though no tag
has been pushed under it yet: the repository has zero tags today.

**Two version numbers now describe one thing.** ADR-0006 observed that the
package version and the plugin version are separate artifacts that *can* drift,
and stopped there. In practice they name the same code delivered through
different channels, and a user comparing `indexkit --version` against the
plugin's `plugin.json` has no way to tell intentional drift from a mistake.
ADR-0005 already treats the plugin `version` as a cache key with strict
`plugin.json` ⇆ `apm.yml` lockstep; leaving the *package* version outside that
discipline puts the least-recoverable artifact under the weakest rule.

## Decision

We will publish `indexkit` from a tag-triggered GitHub Actions workflow that
authenticates to PyPI with **Trusted Publishing (OIDC)** and stores no PyPI
credential, triggered by the tag scheme `docs/releasing.md` already defines:
**`indexkit/v<version>`**. One tag drives both distributions of a release — the
plugin release and the PyPI upload — rather than introducing a second scheme.

The workflow verifies before it publishes: a version-surface guard, the full
test suite, `uv build`, and `twine check --strict` all run in a `verify` job,
and the `publish` job only exists downstream of it. Publishing uploads the
*artifacts `verify` built*, not a rebuild, so what was checked is what ships.

`scripts/release_version.py` reconciles the tag against `pyproject.toml`,
`src/indexkit/__init__.py`, `plugin.json`, `apm.yml`, and a `CHANGELOG.md`
heading. Package and plugin versions are held at **parity by default**, with an
explicit `--allow-plugin-drift` flag as the auditable escape hatch — the same
shape as ADR-0005's `Skip-Version-Bump` trailer. The flag never relaxes the
package surfaces themselves.

`workflow_dispatch` runs verification only and never publishes, so the pipeline
can be rehearsed without spending a tag.

## Options considered

### Credentials — Option A: PyPI Trusted Publishing via OIDC (chosen)

| Dimension | Assessment |
|---|---|
| Standing credential | None — no PyPI secret exists to leak |
| Credential lifetime | Minutes, minted per run |
| Blast radius if CI is compromised | Bounded to the configured workflow + environment |
| Provenance | PEP 740 attestations published automatically |
| Cost | One-time PyPI-side config; binds to the workflow **filename** |

### Credentials — Option B: PyPI API token in a repository secret

**Pros:** Works today with no PyPI-side setup, is portable to other CI systems,
and keeps the workflow filename free to change.
**Cons:** A long-lived bearer credential for a one-way-door artifact, valid until
someone remembers to rotate it. It is also strictly worse on the axis that
matters here: the failure mode is "someone else published to our name," which no
amount of in-workflow verification can prevent.

### Tag scheme — Option C: reuse `<name>/v<version>` from `docs/releasing.md` (chosen)

| Dimension | Assessment |
|---|---|
| Says what is being released | Yes |
| Independent release cadence per package | Yes |
| Trigger precision | `on.push.tags: indexkit/v*` matches only this package |
| Conventions in the tree | One — the incumbent, extended rather than replaced |
| Cost | Couples the plugin release and the package release to one tag |

### Tag scheme — Option D: a package-specific `<package>-v<version>`

**Pros:** Separates "the plugin was released" from "the package was published",
so a plugin-only release need not imply a PyPI upload. Avoids `/` in ref names,
which a few tools handle awkwardly.
**Cons:** Two tag conventions for one repository, differing by one character, for
artifacts that are the same code. The separation it buys is the same separation
the parity decision below deliberately removes, so paying for it here would be
self-contradictory. This was the initial choice in drafting and was reversed on
finding the incumbent convention.

### Tag scheme — Option E: bare `v<version>`

**Pros:** The convention most tooling and most readers expect; shorter.
**Cons:** Ambiguous in a 14-plugin tree, and it couples publishable components to
a single version line. Releasing `memory` would require inventing a version for
it that does not collide with `indexkit`'s, which is a versioning problem created
purely by the tag format.

### Tag scheme — Option F: no tags; publish on manual `workflow_dispatch`

**Pros:** Nothing to get wrong in a tag; the human states the version directly.
**Cons:** Removes the artifact that ties a release to an immutable commit. Git
history would no longer answer "what was in 0.6.0," and the version becomes a
free-text input — the single most error-prone place to put the one value that
cannot be corrected after upload.

### Version parity — Option G: parity by default, drift by explicit flag (chosen)

**Pros:** One number for one thing; makes accidental drift loud while leaving
deliberate drift possible and recorded in the command that allowed it.
**Cons:** Forces a package release for a plugin-only change and vice versa,
which will occasionally publish a version whose package content is unchanged.

### Version parity — Option H: let the two versions drift freely, per ADR-0006

**Pros:** Honest about them being different artifacts; no coupling; no spurious
releases.
**Cons:** Nothing distinguishes intentional divergence from a missed bump, and
the failure is silent in exactly the way ADR-0005 was written to prevent.

### Option I: Do nothing — keep publishing manual

**Pros:** No pipeline to maintain; a human decides everything.
**Cons:** ADR-0006 is `accepted`, so "do not publish" is not available; and a
manual `twine upload` is the version of this process with the *fewest* checks in
front of the irreversible step.

## Trade-offs

- **Trusted Publishing binds the workflow filename.** The PyPI publisher config
  names `(owner, repo, workflow filename, environment)`. Renaming
  `release-indexkit.yml` silently breaks publishing until PyPI is updated. A
  workflow filename would normally not be worth a decision record; under OIDC it
  becomes a configuration key, and that is why this is listed rather than
  assumed.
- **The `pypi` environment is a gate we have not configured.** The workflow
  declares it; whether it carries a required reviewer is a repository setting,
  not something this record can enforce. Declaring the environment without
  approvers gives provenance scoping but not human review.
- **One tag now means two things.** `indexkit/v0.6.0` triggers the PyPI upload
  *and* is the plugin release tag `docs/releasing.md` describes. That is the
  point — one release, one identifier — but it means a plugin-only release of
  `indexkit` cannot be tagged without also publishing to PyPI. Under the parity
  rule below that is consistent; it would be incoherent without it.
- **`one-way-door` is declared for the tag scheme, not the code.** Tags are
  permanent once pushed and get referenced by release pages, changelog links, and
  attestation subjects. Switching schemes later does not break anything, but it
  leaves two conventions in the history forever.
- **Parity will sometimes publish a no-op package release.** A plugin-only fix
  that bumps `plugin.json` also bumps the package, producing a PyPI version whose
  code is identical to its predecessor. That is real waste, accepted in exchange
  for drift being impossible to introduce silently.
- **`pypa/gh-action-pypi-publish@release/v1` is a moving reference.** It is the
  upstream-documented entry point and is maintained by PyPA, but it is not a
  pinned digest, so a compromised upstream would run in a job that holds an OIDC
  token. Pinning by digest would trade that for a manual upgrade duty.
- **The guard is a static reconciliation, not a build check.** It reads declared
  versions before the build; the filename assertion after `uv build` is what
  catches a backend that ignored them. Neither can detect that the *code* at a
  tag differs from what was reviewed.

## Consequences

- **Easier:** releasing is `git tag -a indexkit/vX.Y.Z && git push --tags`; no
  credential to rotate; a mismatched version fails in the first minute of the
  run rather than in an unrecoverable upload; `memory` gets a release path by
  copying one file and changing two identifiers.
- **Harder:** the release path now has a PyPI-side configuration that lives
  outside this repository, and the workflow filename cannot be changed casually.
- **How we would know this was wrong:** within the first three releases, either
  (a) the parity rule forces a package publish whose sdist is byte-identical to
  its predecessor more than once, or (b) a release is blocked by the guard for a
  reason that is not a real version error. Either indicates the rule costs more
  than the drift it prevents.
- **Revisit if:** a second publishable package lands and the copied workflow
  proves to need meaningful divergence — at which point a reusable workflow is
  the better shape; or if PyPI's Trusted Publishing constraints change such that
  filename binding is no longer implied.

## Action items

1. [ ] **Maintainer-only, before the first tag:** configure a PyPI pending
   publisher for `indexkit` — owner `mbeacom`, repo `context-kit`, workflow
   `release-indexkit.yml`, environment `pypi`. The name was unclaimed as of
   2026-08-08 (verified: `GET /pypi/indexkit/json` returned 404).
2. [ ] Decide whether the `pypi` GitHub environment requires a reviewer, and
   configure it. The workflow cannot enforce this.
3. [ ] Rehearse with `workflow_dispatch` (verification only) before tagging.
4. [ ] When `memory` is packaged (ADR-0006 action item 3), either copy this
   workflow or factor both onto a reusable one; do not add `memory` to the
   `indexkit` trigger.
