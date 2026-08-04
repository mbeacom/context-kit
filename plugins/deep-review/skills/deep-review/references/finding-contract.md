# Finding contract

Every lens emits one `context-kit/review-findings-v1` document. The contract is
what makes findings mergeable, rankable, and routable; adjudication rejects a
report that violates it rather than silently degrading the ledger.

## Document shape

```markdown
---
schema: context-kit/review-findings-v1
lens: <charter id>
artifact: <artifact reference at a pinned revision>
scope_reviewed: [<paths or regions actually read>]
scope_skipped: [{ "region": "<path or region>", "reason": "<why>" }]
---

## Summary

One to three sentences on the artifact as this charter sees it.

## Findings

- [DEFECT] [severity: major] `src/pay/refund.ts:118`
  **Problem:** what is wrong.
  **Consequence:** what goes wrong, for whom, under what conditions.
  **Falsification:** the concrete input, sequence, or state that exhibits it.
  **Resolution:** what would resolve this finding.

## Coverage

What was read, what was not, and why.
```

All three sections are required on every run, including empty ones. Write
`None.` rather than omitting a heading — a report missing a section is
truncated, not terse, and adjudication treats it as a failed lens.

## Required fields by type

| Type | Required fields |
| --- | --- |
| `DEFECT` | Problem, Consequence, Falsification, Resolution |
| `RISK` | Problem, Consequence, Trigger, Resolution |
| `JUDGMENT` | Problem, Consequence, Resolution |
| `QUESTION` | Problem, Resolution |

`Falsification` is the adversarial discipline made structural: a `DEFECT` you
cannot exhibit is a `RISK`. `Trigger` is the condition under which a `RISK`
becomes real; a risk with no trigger is a `JUDGMENT` wearing a warning label.
For a `QUESTION`, `Resolution` is what answer would unblock the judgment.

## Severity

Severity is a property of consequence against the stakes recorded in the frame,
never a distribution to fill out. All four levels being absent is normal.

| Severity | Meaning |
| --- | --- |
| `blocking` | the decision the review supports should not proceed as-is |
| `major` | real harm, but the decision can proceed with a plan to address it |
| `minor` | genuine but low-cost; fix when convenient |
| `note` | observation worth recording; no action implied |

Two calibration rules:

- **Severity is not confidence.** An uncertain finding about a catastrophic
  consequence is still `blocking`; say the uncertainty in `Consequence`.
- **Severity is not effort.** A one-line fix for a data-loss bug is `blocking`.
  Cheapness of the fix belongs in `Resolution`.

## Citations

Every finding cites a location in the artifact as `path:line`, `path:heading`,
or `path` when the finding is about the file as a whole. Cite the original
artifact location even when a shard or derived extract was read — shards are an
execution detail that will not exist when someone reads the report.

A finding whose citation is `none` is only valid as a `QUESTION` about a
missing thing, and must say in `Problem` what was expected and where.
Adjudication rejects `none` for every other type: a `DEFECT` routed to `verify`
with no location gives the verifier nowhere to look.

The report's `artifact` must be present and must match the frame's pinned
revision. A report from another revision cites lines that may no longer exist,
so merging it would present stale locations — and stale corroboration — under
this panel's artifact.

`scope_reviewed` and `scope_skipped` must be well-formed JSON. A malformed scope
field is a contract error rather than an empty list, because coverage is what
bounds how a reader may interpret the panel's silence.

The Findings section must contain either the `None.` placeholder or fully parsed
finding blocks. Stray prose there is rejected: a truncated report that returned
no parsable findings would otherwise be indistinguishable from a lens that
genuinely found nothing.

## Honesty rules

- **Report zero findings plainly.** A charter with nothing to say is a normal,
  useful result. Padding a report with marginal findings corrupts the ledger and
  trains readers to skim past real ones.
- **Never assert what you did not read.** If part of the artifact was skipped,
  it goes in `scope_skipped` with a reason and is reported, not implied.
- **Stop early and say so.** A worker that runs out of context lists the
  unreviewed regions under Coverage rather than judging them from filenames.
- **Do not grade the author.** Cite the work; intent and competence are not
  reviewable artifacts.
