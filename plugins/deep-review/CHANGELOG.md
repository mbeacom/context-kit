# Changelog

## 0.1.1 — 2026-08-04

Review of the initial implementation found six ways the adjudicator could
report a degraded panel as a clean one. All six are now regression-tested.

- **Corroboration no longer swallows a conflicting fix.** Merging kept only the
  cluster head's fields, so two lenses that agreed on a problem but proposed
  opposite resolutions collapsed into one entry with the dissenting position
  discarded and no tradeoff emitted — the exact outcome this plugin exists to
  prevent. Each member's resolution is now retained on the entry, and conflict
  detection runs over individual lens positions rather than merged entries. A
  candidate found this way is marked `within_finding`.
- Stray prose in a Findings section is rejected instead of parsed as zero
  findings. A worker that stopped mid-report could previously exit clean.
- A lens report must carry an `artifact` matching the frame's pinned revision,
  so a stale report from another revision cannot contribute citations and
  corroboration to this panel.
- Malformed `scope_reviewed` / `scope_skipped` values are contract errors rather
  than silently emptied lists, since coverage is what bounds how a reader may
  interpret silence.
- Citation `none` is rejected for every type except `QUESTION`, so a `DEFECT`
  cannot reach `verify` with no location to inspect.
- Risks are queued as `routing.risk_triage` rather than `routing.runtime_evidence`.
  Only a risk whose trigger is observable can be settled by running something,
  and a maintenance or adoption risk has a real trigger no command can
  reproduce; the ledger now reports the queue instead of claiming the
  destination.

## 0.1.0 — 2026-08-03

- Initial release: multi-lens evaluative review as a capability distinct from
  claim verification and corpus coverage. Retrieval finds material, `verify`
  settles whether a claim is true, `corpus-review` proves everything was read;
  this answers whether the work is good and what will go wrong.
- `deep-review` skill: the frame → select lenses → dispatch → adjudicate →
  route → report pipeline, the finding-type taxonomy (`defect`, `risk`,
  `judgment`, `question`) that decides how each finding is settled, and the
  rules that keep a panel from degrading into volume, manufactured
  disagreement, or preference laundering.
- `review-lens` agent: one read-only worker parameterized by a lens charter
  rather than one agent per persona, so callers can add a domain lens without
  shipping a new component. Its output contract requires a `Falsification` for
  every `DEFECT` and a `Trigger` for every `RISK`, making the "falsify or
  downgrade" discipline structural instead of advisory.
- `/deep-review` command for the end-to-end run.
- `adjudicate-findings.py` merges corroborating findings into one entry that
  keeps the highest severity any lens asserted, so agreement raises confidence
  without raising count — the signal a panel exists to produce.
- Findings from different lenses at one citation with dissimilar resolutions
  surface as **tradeoff candidates** for a human decision. They are never
  auto-resolved: silently picking a winner discards the most valuable output of
  a multi-perspective review.
- The frame's `expected_lenses` roster is required, and a declared lens with no
  report exits nonzero and is named in the report's "Degraded review" section. A
  crashed lens is otherwise indistinguishable from a lens that found nothing,
  which would let a failed operator review read as an operable artifact.
- Findings that fail the contract are counted as rejected and excluded from the
  ledger's findings list, so an unfalsified defect cannot reach the report.
- Adjudication refuses to write into the findings directory, since a ledger
  written beside the lens reports would be parsed as a lens report on re-run.
- Merge clustering compares each candidate against a cluster's fixed
  representative rather than any member, so the ledger does not depend on the
  order lens reports happen to be read in.
