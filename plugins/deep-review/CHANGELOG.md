# Changelog

## 0.2.1 — 2026-08-04

- Shorten the `deep-review` skill trigger to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.2.0 — 2026-08-04

Field use surfaced the plugin's own version of the failure it exists to prevent:
the four lenses ran, but their reports stayed inline, adjudication was skipped,
and the resulting hand-written synthesis was formally indistinguishable from an
adjudicated one. Only the operator's own footnote disclosed it.

- **`--findings-file` accepts one bundled file** holding every report verbatim.
  Workers reply inline, so requiring one file per lens put filesystem work
  between the panel and its own guarantees, and skipping that work was the path
  of least resistance. Bundled and per-file input produce identical ledgers.
  Documents split on a `---` fence whose first field is `schema:`, with fenced
  code blocks tracked so a report quoting the contract cannot split itself.
- **A lens whose findings are all `QUESTION` is flagged `question_dominated`**
  and named under "Degraded review". Lenses that lack the access their charter
  needs correctly return questions rather than guesses, but a panel of nothing
  but questions previously reported zero defects and read as clean. Its silence
  now says *could not look*, not *nothing to find*. A lens with no findings at
  all is untouched: that is a genuine clean result.
- **A synthesis produced without the adjudicator must be labeled an
  "Unadjudicated synthesis"** naming what is absent — corroboration unmerged,
  resolution conflicts undetected, coverage uncomputed. Documented in the
  command, skill, references, and both READMEs.
- The command's persist step is now explicit and verified against the
  `expected_lenses` roster instead of a single trailing sentence, and both the
  command and skill state that an early decisive finding is a reason to run
  adjudication rather than to stop.
- The `review-lens` agent must name missing access under Coverage when a tool it
  lacked forced a `QUESTION`, so the reader can separate an under-equipped lens
  from an unclear artifact.

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
