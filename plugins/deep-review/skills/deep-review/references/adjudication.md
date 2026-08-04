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

## Input modes

`--findings-dir` reads one `<lens>.md` per lens. `--findings-file` reads a
single file holding every report concatenated verbatim, which is what an
orchestrator has when workers returned their documents inline. Exactly one is
required.

The bundle mode exists because the per-file requirement had a cost: needing N
writes before adjudication could run made skipping the step the path of least
resistance, and a skipped adjudication produces a synthesis that carries none
of the guarantees below while looking exactly like one that does. Documents
split on a `---` fence whose first field is `schema:`, with fenced code blocks
tracked so a report quoting the contract does not split itself.

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

Merging a problem never merges away a fix. Each member's own `Resolution` is
retained on the entry, and conflict detection runs over those individual lens
positions rather than over merged entries. Two lenses can agree completely
about what is wrong and still want opposite things done about it; comparing
only merged entries would let corroboration hide that disagreement entirely,
which is the one outcome this pipeline must never produce.

Corroboration is meaningful only because lenses cannot see each other. A panel
run with shared visibility produces agreement that means nothing, and this
number should be ignored.

## Tradeoff candidates

Two positions from **different lenses** at the same citation whose `Resolution`
texts are dissimilar are flagged as a **tradeoff candidate**: two lenses want
different things in the same place. This holds whether they raised separate
findings or were merged into one — a candidate marked `within_finding` is the
second case, where the lenses agreed on the problem and split on the fix.

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
  every `RISK`, listed for triage. Risks are queued, not routed: only a risk
  whose trigger is *observable* can be settled by running something, and a
  maintenance or adoption risk has a real trigger that no command can
  reproduce. Classifying a prose trigger is a judgment the routing step makes,
  so the ledger reports the queue rather than claiming the destination.
- **Coverage** — per lens, the regions reviewed and the regions skipped with
  reasons, plus any declared lens that reported nothing.
- **Question-dominated lenses** — lenses whose findings were *all* questions.

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
- **A question-dominated lens judged nothing.** A lens that only asked
  questions reached no verdict, usually because it lacked access its charter
  needed. Its zero defects mean *could not look*, not *nothing to find*.
- **No ledger means no guarantees.** A synthesis written without running this
  script has unmerged corroboration, undetected resolution conflicts, and no
  coverage accounting. It may still be useful, but it must be labeled an
  **Unadjudicated synthesis** — nothing in its shape distinguishes it from an
  adjudicated one, so only the label keeps it honest.
