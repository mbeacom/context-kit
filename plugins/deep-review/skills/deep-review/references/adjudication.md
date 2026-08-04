# Adjudication

Adjudication turns independent per-lens reports into one review. It is
deterministic and standard-library only: no model runs, and the same inputs
always produce the same ledger.

```bash
python3 "${CONTEXT_KIT_DEEP_REVIEW_ROOT}/scripts/adjudicate-findings.py" \
  --frame "<work dir>/frame.json" \
  --findings-dir "<work dir>/findings" \
  --out-dir "<work dir>/report"
```

## The frame is the denominator

`frame.json` is a `context-kit/review-frame-v1` document naming the artifact,
the decision, the stakes, and the **expected lenses**. That last field is what
makes a missing lens reportable: without a declared roster, a worker that
crashed looks identical to a worker that found nothing.

Adjudication exits nonzero when a declared lens has no report, when a report is
malformed, or when a finding violates the contract. A degraded review is
reported as degraded; it is never quietly averaged into a clean one.

## Fingerprinting

Each finding is fingerprinted from its type, its normalized citation, and a
content signature of its `Problem` text — lowercased alphanumeric tokens with
boilerplate stopwords removed. Citations normalize by collapsing whitespace and
stripping surrounding backticks, so `src/a.ts:10` and `` `src/a.ts:10` `` are
the same location.

Fingerprinting is a merge heuristic, not a semantic-equivalence claim. It is
tuned to under-merge: two findings wrongly kept separate are visible in the
report, while two wrongly merged are invisible.

## Corroboration

Two findings **corroborate** when they share a type, share a normalized
citation, and their `Problem` token sets reach the similarity threshold.
Corroborated findings collapse into one entry that lists every lens that raised
it and keeps the highest severity asserted by any of them.

Corroboration raises confidence; it never raises count. Independent lenses
converging on the same problem is the strongest signal a panel produces, and
counting it three times destroys exactly that signal by making agreement
indistinguishable from volume.

Corroboration is meaningful only because lenses cannot see each other. A panel
run with shared visibility produces agreement that means nothing, and this
number should be ignored.

## Tradeoff candidates

Two findings from **different lenses** at the same citation whose `Resolution`
texts are dissimilar are flagged as a **tradeoff candidate**: two lenses want
different things in the same place.

These are reported as candidates, not proven contradictions. Deciding whether
two prose resolutions genuinely conflict is not a deterministic operation, and
the script does not pretend otherwise. The value is in surfacing the collision
for a human rather than letting a synthesizer silently pick a winner — the
single most common way a multi-perspective review loses its most useful output.

A tradeoff candidate is never auto-resolved, never merged, and never downgraded
to a finding. It routes to whoever owns the decision.

## The review ledger

The ledger is a `context-kit/review-ledger-v1` document reporting:

- **Counts** by type, by severity, and by lens, after merging.
- **Corroborated findings** — how many entries carry more than one lens.
- **Tradeoff candidates** — collisions awaiting a human decision.
- **Routing queue** — every `DEFECT`, listed for `verify` adjudication, and
  every `RISK` whose trigger is observable, listed as a `runtime-evidence`
  candidate.
- **Coverage** — per lens, the regions reviewed and the regions skipped with
  reasons, plus any declared lens that reported nothing.

## Reading the ledger honestly

- **A clean ledger is not an approval.** It reports what the declared lenses
  looked at. Coverage gaps and skipped regions bound what silence means.
- **Counts are not quality.** Ten `note` findings and one `blocking` finding is
  not eleven problems. Rank by severity against the stakes, then stop.
- **Unrouted defects are unfinished work.** A `DEFECT` that has not been through
  `verify` is a hypothesis. Reporting it as a confirmed problem is exactly the
  overreach this plugin exists to prevent.
- **A missing lens invalidates its charter's silence.** If the operator lens
  failed, the review says nothing about operability — it does not say the
  artifact is operable.
