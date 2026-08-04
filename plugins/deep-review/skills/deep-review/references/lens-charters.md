# Lens charters

A lens is a **charter**, not a personality. Personas drift toward voice and
mannerism; charters state responsibility and, crucially, what the lens must not
comment on. The non-scope is what stops four lenses from all filing the same
naming complaint.

Every charter has three fields:

- **Responsibility** — what this lens is accountable for noticing. If it misses
  something here, the panel failed.
- **Non-scope** — what it must stay silent about, because another lens owns it
  or because it is not this review's business.
- **Evidence** — what it may read beyond the artifact itself.

## Default charters

### `adversarial`

- **Responsibility** — make the artifact fail. Boundary and degenerate inputs,
  unhandled error paths, concurrency and ordering, resource exhaustion, trust
  boundaries, state left inconsistent after partial failure.
- **Non-scope** — style, naming, structure, documentation quality, long-term
  design direction.
- **Evidence** — the artifact, its callers and callees, existing tests, and the
  history of past failures in the same area.
- **Hard rule** — exhibit a concrete failing input, sequence, or state, or file
  the finding as a `risk`. "This could break under load" without a mechanism is
  not an adversarial finding; it is an anxiety.

### `architect`

- **Responsibility** — coherence with the system that already exists. Coupling
  and boundary placement, duplicated or contradicted abstractions, precedent
  this change sets for future work, migration and evolution cost.
- **Non-scope** — bug hunting, runtime failure modes, operational tooling,
  end-user wording.
- **Evidence** — sibling modules, existing patterns, prior decisions recalled
  from `memory`, and the artifact's stated design intent.
- **Hard rule** — cite the existing precedent the change agrees or conflicts
  with. An architectural finding with no comparison point is a preference.

### `consumer`

- **Responsibility** — the artifact as experienced by whoever must use it. For a
  library that is the calling developer: API shape, defaults, failure messages,
  migration burden. For a product surface it is the end user: comprehensibility,
  recoverability from mistakes, and whether the common path is the easy one.
- **Non-scope** — internal structure, implementation quality, deployment.
- **Evidence** — public surfaces, docs, error strings, examples, changelog, and
  anything a user would plausibly read before asking for help.
- **Hard rule** — describe the concrete moment of use where the problem is felt.
  "The API is confusing" is not a finding; "a caller who omits `timeout` gets a
  null pointer error rather than a default" is.

### `operator`

- **Responsibility** — day two. Whether a failure here is detectable,
  diagnosable, reversible, and survivable: logging and signals, blast radius of
  a bad deploy, rollback and migration reversibility, dependency and quota
  assumptions, on-call burden.
- **Non-scope** — design elegance, API taste, code style.
- **Evidence** — configuration, deployment manifests, migrations, health checks,
  alerting rules, and runbooks.
- **Hard rule** — name the failure you are asked to diagnose at 3am and the
  signal that would let you. This is the lens most often missing from AI review,
  and the one whose absence is discovered in production.

## Domain charters

Add a domain lens when the stakes call for expertise none of the defaults own —
security, accessibility, privacy, cost, internationalization, regulatory. Write
it with the same three fields, and give it a non-scope that keeps it out of the
defaults' territory.

A domain lens without a non-scope will duplicate the adversarial lens, because
every domain concern can be phrased as a way things break.

## Selecting lenses

- **Match lenses to stakes, not to a ritual.** A docs-only change does not need
  an operator lens. Running one produces filler, which trains readers to skim.
- **Run at least two.** One lens is a review, not a panel; corroboration and
  tradeoff detection both need a second independent read.
- **Cap the panel.** Beyond four or five lenses, marginal findings fall and
  adjudication cost rises. Add a lens because a concern is unowned, never for
  symmetry.
- **Never let a lens read another lens.** Independence is the entire source of
  the corroboration signal. A lens that sees prior findings anchors to them and
  its agreement becomes worthless as evidence.

## Writing a brief

A worker brief is self-contained. It carries the frame, one charter, the
artifact location at a pinned revision, the finding contract, and nothing about
any other lens. A worker that has to ask what it is reviewing has already been
briefed badly.
