---
name: corpus-review
description: "Use when every unit of a corpus must be accounted for rather than merely searched — auditing a document set, log archive, or file tree with provable coverage and gaps split into truly absent versus undecidable."
license: MIT
compatibility: "The bundled scripts require Python 3 and use only the standard library. Extraction of non-text units (PDF, Office, archives) depends on separately installed tools from the data-and-docs-search skill."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash Task
---

# Corpus Review

Review a corpus that is too large to read in one context, and report what was
actually inspected. Retrieval answers *where is the relevant material*; this
capability answers *what does all of it contain, and what is still unaccounted
for*.

Use it when the deliverable requires coverage rather than hits:

- "Audit every deployment runbook for the deprecated rotation step."
- "Go through all 800 pages we received and tag anything that contradicts the
  timeline."
- "Review the whole log archive for occurrences of this failure mode."
- "Check every service manifest for a missing ownership label."

Use retrieval instead — `retrieval-strategy`, `code-search`, `local-rag` — when
a representative answer is enough and no one will act on the absence of a hit.
Use `change-impact` instead when the question is the blast radius of a proposed
change; that skill deliberately stops at useful coverage.

## Boundary

- Reading, sharding, dispatching, and aggregating are in scope. Editing corpus
  units, remediating them, or acting on findings is not.
- Coverage is measured, never assumed. An unread unit is reported as unread.
- This skill does not define what a finding means. The caller supplies the
  review question and finding taxonomy; the pipeline preserves them.

## Pipeline

### 1. Frame

Record before enumerating anything:

- **Review question** — one statement of what every unit is being read *for*.
- **Scope rules** — the include and exclude patterns, stated as rules rather
  than applied silently, so an excluded unit is accountable rather than absent.
- **Finding taxonomy** — the tags or categories a worker may emit, and what
  makes a finding significant.
- **Expected inventory**, when one exists — the list of things that *should* be
  present. This is what makes absence reportable at all.

Without a stated review question this is retrieval, not review. Stop and ask.

### 2. Inventory

Enumerate the corpus into units with stable identity:

```bash
python3 "${CONTEXT_KIT_CORPUS_REVIEW_ROOT}/scripts/inventory-corpus.py" \
  --root "<corpus root>" \
  --out "<work dir>/inventory.json" \
  --include '**/*.md' --exclude '**/node_modules/**'
```

Each unit carries a path, byte size, SHA-256, and an inspectability signal.
The hash is what makes resumption safe and makes a later re-run detect drift.
See `references/inventory-contract.md`.

### 3. Shard

Group units into work units that fit a worker's context:

```bash
python3 "${CONTEXT_KIT_CORPUS_REVIEW_ROOT}/scripts/plan-shards.py" \
  --inventory "<work dir>/inventory.json" \
  --out "<work dir>/shards.json" \
  --max-bytes 200000 --max-units 25
```

Every shard records the original location of everything in it. A worker may
read a derived artifact, but a finding cites the original unit — never the
shard. See `references/shard-dispatch.md`.

### 4. Dispatch

One `corpus-reviewer` worker per shard, each with a self-contained brief: the
review question, the finding taxonomy, its shard's units, and its output path.
Send independent workers in one batch rather than sequentially.

Workers are resumable. A shard whose findings file already matches the recorded
shard digest is skipped, so an interrupted run resumes instead of re-reading.

### 5. Aggregate

```bash
python3 "${CONTEXT_KIT_CORPUS_REVIEW_ROOT}/scripts/aggregate-findings.py" \
  --inventory "<work dir>/inventory.json" \
  --shards "<work dir>/shards.json" \
  --findings-dir "<work dir>/findings" \
  --out-dir "<work dir>/report"
```

Aggregation merges findings and computes the coverage ledger. It exits nonzero
while any unit is `pending` or `failed`, so an incomplete run cannot be reported
as a complete one. See `references/coverage-ledger.md`.

### 6. Report

Report findings **and** the ledger together. A findings list without coverage
invites the reader to assume the corpus was fully read.

## Disposition vocabulary

Every unit ends in exactly one disposition:

| Disposition | Meaning |
| --- | --- |
| `reviewed` | inspected in full against the review question |
| `partial` | inspected, but a bounded portion was not inspectable |
| `uninspectable` | present, but the content could not be read at all |
| `out_of_scope` | excluded by a stated scope rule, not by omission |
| `failed` | dispatch or extraction error; retryable |
| `pending` | not yet attempted |

`uninspectable` covers encrypted, image-only, corrupt, truncated, and
unsupported-binary units. It is a scope constraint, not a review failure — route
it to remediation rather than hiding it.

## Absence discipline

The single most consequential output of a corpus review is what is *missing*.
Two verdicts, never one:

- **`not-found`** — absent from material that was actually inspectable. A real
  gap, safe to act on.
- **`indeterminate`** — absent, but coverage over the units that would contain
  it is too weak to call it absent.

**`indeterminate` outranks `not-found`.** If any `uninspectable`, `partial`,
`failed`, or `pending` unit could plausibly hold the expected item, the verdict
is `indeterminate`. A `partial` unit blocks a gap for the same reason an
`uninspectable` one does — its unread portion could contain the item. Never
report something as missing solely because a search over partially readable
material returned nothing.

With no expected inventory, or with no unit in scope at all, absence verdicts
are reported as unavailable rather than inferred. Scope rules that match nothing
produce zero coverage, not a corpus full of gaps.

This is `verify`'s `unable-to-check` verdict raised from a single claim to a
whole corpus. Route `indeterminate` items to remediation — a cleaner copy, an
extraction tool, a re-request, or human inspection — before treating absence as
evidence.

## Practices

1. **Frame before enumerating.** A review question written after the findings
   is a rationalization of what the workers happened to notice.
2. **Cite original locations.** Sharding is an execution detail; provenance is
   not. A finding that cites a derived artifact is unusable once shards are
   regenerated.
3. **Shard by budget, not by count.** Bound bytes and units per shard so a
   single oversized unit cannot silently exceed a worker's context.
4. **Prefer cheap workers.** Reading is mechanical; use `plan-execute` to pin
   workers to a cheaper model while a strong model frames and synthesizes.
5. **Keep derived artifacts out of the corpus root.** Write shards, findings,
   logs, and reports to a separate work directory so a re-run enumerates the
   same corpus.
6. **Sample before committing.** On an unfamiliar corpus, run one shard end to
   end and read its findings before dispatching the rest.
7. **Report the denominator.** "41 findings" means nothing without "across 612
   of 640 units; 19 uninspectable, 9 out of scope."

## Composition

- **`verify`** — check a consequential finding before it is acted on, and reuse
  its evidence discipline. A finding cites a unit and a location, not a memory.
- **`plan-execute`** — supplies the worker fan-out and the cheap-worker /
  strong-synthesizer split this pipeline depends on.
- **`code-search`** — `data-and-docs-search` extracts non-text units; `rg` pins
  exact lines inside a unit a worker flagged.
- **`retrieval-strategy`** — decides whether the task needs review at all.
  Reach for retrieval first; escalate to review when absence must be provable.
- **`context-handoff`** — a long review spans sessions. The work directory plus
  the shard plan is the resumable state; hand off the frame and the ledger.

## References

- **`references/inventory-contract.md`** — unit identity, inspectability
  signals, and the inventory schema.
- **`references/shard-dispatch.md`** — shard budgets, worker briefs,
  resumability, and bounded concurrency.
- **`references/coverage-ledger.md`** — the ledger schema, coverage arithmetic,
  and absence-verdict rules.
