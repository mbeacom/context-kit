# Coverage Ledger

The ledger is the part of a corpus review that cannot be faked. Findings are
interesting; the ledger is what makes them interpretable.

## Every unit is accounted for

The ledger assigns exactly one disposition to every unit in the inventory, and
the dispositions sum to the inventory total. That identity is the whole point —
if the dispositions do not sum, the review has an unaccounted hole.

| Disposition | Assigned when |
| --- | --- |
| `reviewed` | a worker listed the unit in `units_reviewed` |
| `partial` | reviewed, with a bounded portion recorded as unreadable |
| `uninspectable` | listed in `units_uninspectable` with a reason |
| `out_of_scope` | excluded by a stated scope rule at inventory time |
| `failed` | its shard errored, or its findings file is malformed |
| `pending` | in a shard with no findings file, or omitted by its worker |

`pending` is the default. A unit is only promoted out of it by an explicit
statement from a worker, so silence never counts as coverage.

## Arithmetic

Report both, and never only the first:

```text
unit coverage  = reviewed / (total - out_of_scope)
byte coverage  = reviewed_bytes / (total_bytes - out_of_scope_bytes)
```

Only `reviewed` counts toward coverage. `partial` is reported separately
because part of it was never read, and rolling it into the numerator would
overstate exactly what the ledger exists to measure.

Unit coverage alone hides a skipped 4 MB archive among 600 small files. Byte
coverage alone hides 40 skipped one-line configs. A review is complete only when
`pending`, `failed`, and `stale_digest` are all zero **and** at least one unit
was in scope; `uninspectable` and `partial` may be nonzero, but each must be
reported and routed.

`complete` answers a narrow question — is there work left to re-dispatch? It is
not a claim that most of the corpus was read. A run can be complete with 1%
coverage if the rest is `partial` or `uninspectable`, which is why `findings.md`
carries its own coverage caveat rather than trusting `complete` alone.

Out-of-scope units are excluded from the denominator because they were never
meant to be read — but they stay in the ledger with their rule, so a reader can
challenge the scope rather than discover it later.

## Absence verdicts

For each item in the expected inventory that no worker found:

- **`not-found`** — every unit that could plausibly contain it was `reviewed`,
  and none did. A real gap, safe to act on.
- **`indeterminate`** — at least one unit that could plausibly contain it is
  `uninspectable`, `partial`, `failed`, or `pending`. Absence is not decidable
  yet.

**`indeterminate` outranks `not-found`.** Downgrading it — treating an unread
unit as if it had been read and found empty — is the characteristic failure of
automated review, and it is the one that causes real harm: the gap gets acted on
as a fact.

`partial` blocks a `not-found` for exactly the same reason `uninspectable` does:
the unread portion of a partially readable unit could hold the expected item. A
unit that is 99% unreadable still counts as `partial`, so a `partial` unit is
never treated as evidence of absence.

When no expected inventory was supplied, the ledger reports absence verdicts as
unavailable rather than inferring them. The same applies when no unit was in
scope at all — scope rules that match nothing produce zero coverage, not a
corpus full of gaps. Absence is only meaningful relative to something that was
expected *and* material that was actually read.

## Schema

```json
{
  "schema": "context-kit/corpus-coverage-v1",
  "generated_at": "2026-07-25T12:00:00+00:00",
  "inventory_sha256": "…",
  "complete": false,
  "dispositions": {
    "reviewed": 601,
    "partial": 2,
    "uninspectable": 19,
    "out_of_scope": 9,
    "failed": 1,
    "pending": 8
  },
  "coverage": { "units": 0.9524, "bytes": 0.9871 },
  "shards": {
    "total": 32,
    "complete": 30,
    "failed": 1,
    "pending": 1,
    "stale_digest": 0
  },
  "uninspectable": [
    { "id": "u0104", "path": "scans/intake-07.pdf", "reason": "no text layer" }
  ],
  "absence": {
    "available": true,
    "not_found": ["signed acknowledgement"],
    "indeterminate": [
      {
        "item": "incident report",
        "reason": "19 uninspectable units in the matching date range"
      }
    ]
  }
}
```

`complete` is `true` only when `pending`, `failed`, and `stale_digest` are all
zero and the in-scope denominator is nonzero. A scope rule that matched nothing
is not a finished review — it read no material — so it reports `complete: false`
with a warning. `aggregate-findings.py` exits nonzero when `complete` is
`false`, so a caller cannot report such a run as finished without passing
`--allow-incomplete` and acknowledging it.

## Routing the ledger

Each bucket has a different next action. Reporting them as one list loses that.

| Bucket | Action |
| --- | --- |
| `uninspectable` | remediate — extraction tool, cleaner copy, human inspection |
| `partial` | remediate the unread portion, or accept it as a stated limitation |
| `failed` | retry the shard; investigate if it fails again |
| `pending` | finish the run |
| `out_of_scope` | confirm the scope rule was right |
| `indeterminate` absence | resolve the blocking units before claiming a gap |
| `not-found` absence | act on it — request, escalate, or record the gap |

## Reporting

State the denominator in the same breath as the findings:

> 41 findings across 601 of 631 in-scope units (95.2% by unit, 98.7% by byte).
> 19 units are uninspectable — scanned PDFs with no text layer — and 1 shard
> failed. Two expected items are `indeterminate`, not missing: the uninspectable
> scans fall in their date range.

A findings count without a denominator reads as exhaustive whether or not it is.
That is the misreading the ledger exists to prevent.
