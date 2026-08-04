---
description: Review a change, design, or plan through independent lenses with typed findings and preserved tradeoffs.
argument-hint: "[artifact]"
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3:*), Bash(git:*)
---

Run a multi-lens deep review over `$ARGUMENTS`, or ask what the artifact is when
the argument is empty.

Use this when the deliverable is judgment. If the question is whether specific
statements are true, stop and use `verify` instead. If the deliverable is
provable coverage over many units, use `corpus-review` instead. Say which one
you are switching to rather than running a panel anyway.

## 1. Frame

Collect and restate before dispatching anything:

- The **artifact** at a pinned revision. For a working tree, capture the base
  and head refs so findings stay citable after the tree moves.
- The **decision** this review supports — merge, ship, adopt.
- The **stakes** — what a missed defect costs here. This calibrates severity.
- **Settled constraints** that are not up for relitigation. Recall them from
  `memory` when that plugin is installed.
- The **review scope** — what is in and out. Out-of-scope areas are reported as
  unreviewed, not silently dropped.
- A **work directory** outside the artifact for the frame, findings, and report.

Persist the frame as `context-kit/review-frame-v1` at `<work>/frame.json`,
including `expected_lenses`. That roster is what makes a crashed lens
distinguishable from a lens that found nothing.

If the decision or the stakes are missing, ask. Do not infer them from the diff.

## 2. Select lenses

Choose charters from the `deep-review` skill's `references/lens-charters.md` —
`adversarial`, `architect`, `consumer`, `operator` — and add a domain charter
(security, accessibility, privacy, cost) when the stakes call for one.

Match lenses to stakes rather than running all of them by ritual. Run at least
two; corroboration and tradeoff detection both need a second independent read.
Do not run a lens whose charter has no bearing on the artifact.

## 3. Dispatch

Send one `review-lens` worker per charter **in a single batch**. Each brief is
self-contained: the frame, that one charter, the artifact location, and the
finding contract.

Never show a worker another worker's findings. Independence is the only reason
corroboration carries information.

Persist what each worker returned. Workers reply inline, so this step is what
connects them to the deterministic spine — skipping it is how a panel ends up
hand-synthesized. Either write one file per lens to `<work>/findings/<lens>.md`,
or write every returned document verbatim, frontmatter included, into a single
`<work>/findings.md` bundle. Do not summarize, reformat, or merge them here.

Before continuing, confirm the number of persisted reports matches the roster in
`expected_lenses`.

## 4. Adjudicate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adjudicate-findings.py" \
  --frame "<work>/frame.json" \
  --findings-dir "<work>/findings" \
  --out-dir "<work>/report"
```

Pass `--findings-file "<work>/findings.md"` instead when you bundled the reports
into one file.

**Run this even when a finding already looks decisive.** Merging, conflict
detection, and coverage accounting are not summaries of what you already read —
they are the only things that catch a fix two lenses disagree about, and a lens
that judged nothing. A blocking defect found early is a reason to run
adjudication, not a reason to stop.

A nonzero exit means the review is degraded, not that the artifact is bad: a
declared lens is missing, a report is malformed, or a finding violates the
contract. Re-dispatch the named lens rather than reporting a partial panel as
complete.

If you genuinely cannot run it — no Python, no write access — say so in the
report under the heading **Unadjudicated synthesis**, and state plainly that
corroboration was not merged, resolution conflicts were not detected, and
coverage was not computed. A synthesis without the ledger may be useful, but it
carries none of this plugin's guarantees, and a reader cannot tell the
difference unless you write it down.

## 5. Route

- Every `DEFECT` goes to `verify` as a claim before anyone acts on it. Bring the
  verdicts back into the report; do not grade them yourself.
- A `RISK` whose trigger is observable and unresolved by static reading goes to
  `runtime-evidence`.
- **Tradeoff candidates go to the human.** Present both positions and the
  decision they imply. Do not pick a winner.
- Answer `QUESTION` findings, then re-run only the affected lens.

## 6. Report

Present, in order:

1. The decision this review supports and the top findings by severity.
2. Corroborated findings, naming which lenses converged.
3. Unresolved tradeoffs awaiting a decision.
4. The routing queue and any verdicts already returned.
5. Coverage — what was reviewed, what was skipped, any lens that failed, and any
   lens the ledger flagged as question-dominated.

State findings and coverage together. A findings list alone reads as approval of
everything it does not mention.

A lens flagged `question_dominated` judged nothing: it asked questions and
reached no verdict. Report its zero defects as *could not look*, never as
*nothing to find*. That usually means the lens lacked access its charter needed
— answer the questions or grant the access, then re-run that lens.

Every report is one of two things, and it must say which. Either it carries the
adjudicated ledger, or it is an **Unadjudicated synthesis** whose corroboration,
conflicts, and coverage were never computed. Presenting the second as though it
were the first is the exact failure this plugin exists to prevent, applied to
the plugin itself.
