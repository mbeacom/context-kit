---
name: deep-review
description: "Use when a change, design, plan, or document needs evaluative judgment rather than fact-checking — adversarial, architectural, consumer, and operator critique returning typed findings, merged corroboration, and preserved tradeoffs."
license: MIT
compatibility: "The bundled adjudication script requires Python 3 and uses only the standard library. Routing `defect` findings to adjudication requires the `verify` plugin; per-lens fan-out is cheapest with `plan-execute`."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash Task
---

# Deep Review

Review a work product for **quality and consequence**, not for truth or
coverage. Retrieval finds material, `verify` settles whether a claim is true,
`corpus-review` proves everything was read — this answers the remaining
question: *is this good, and what will go wrong?*

Use it when judgment is the deliverable:

- "Review this pull request before I merge it."
- "Critique this migration design and tell me what breaks in production."
- "Red-team this API before we publish it."
- "Is this RFC coherent with how the rest of the system works?"

Use `verify` instead when the question is whether specific statements hold up.
Use `corpus-review` instead when the deliverable is provable coverage over many
units. Use `change-impact` instead when the question is the blast radius of a
change rather than its quality.

## Why this needs machinery

An unstructured multi-perspective review degrades in three predictable ways, and
each rule below exists to block one:

1. **Volume as rigor.** More findings read as more diligence, so reviewers pad.
2. **Manufactured disagreement.** Distinct personas invent distinct objections
   even when they agree, and the same issue is counted three times.
3. **Preference laundering.** A style opinion is phrased as a defect, and the
   author cannot tell what they are allowed to decline.

A review is useful only when each finding is falsifiable, dispositioned, and
attached to a consequence.

## Boundary

- Reviewing, typing, merging, and reporting are in scope. Fixing the artifact,
  deciding tradeoffs on the author's behalf, and approving a merge are not.
- This skill produces **judgment**, not verdicts. A finding that asserts
  something checkable is routed to `verify`, which owns truth.
- The artifact's own framing is input, never evidence. A description claiming
  "this is backward compatible" is a claim to check, not a premise to accept.
- Zero findings is a valid, reportable result. There is no finding quota.

## Finding types

Every finding declares exactly one type, which determines how it is settled:

| Type | Meaning | Settled by |
| --- | --- | --- |
| `defect` | a checkable assertion that the artifact is wrong | `verify`, with a per-claim verdict |
| `risk` | a conditional prediction; must name the trigger condition | judgment, or `runtime-evidence` when observable |
| `judgment` | a tradeoff or preference with no fact of the matter | the author, who may decline it |
| `question` | the reviewer lacks context needed to judge | an answer, not a fix |

The type is a commitment, not a hedge. A `defect` that survives no attempt at
falsification is a `risk`. A `risk` with no stated trigger is a `judgment`. A
`judgment` presented as a `defect` is the failure mode this taxonomy exists to
prevent. See `references/finding-contract.md` for severity and the required
fields.

## Pipeline

### 1. Frame

Record before any lens reads anything:

- **Artifact** — the exact diff, files, design doc, or plan under review, at a
  pinned revision. A moving artifact makes findings uncitable.
- **Decision it supports** — merge, ship, fund, adopt. Review without a decision
  produces uniform nitpicking because nothing can be ranked.
- **Stakes** — what a missed defect costs here. This calibrates severity;
  without it every finding drifts toward `major`.
- **Settled constraints** — decisions already made that are not up for
  relitigation. Recall them with `memory` when available. An AI reviewer's most
  common failure is reopening a closed tradeoff.
- **Review scope** — what is in and out. Out-of-scope areas are reported as
  unreviewed, not silently skipped.

### 2. Select lenses

Choose from the default charters in `references/lens-charters.md`
(`adversarial`, `architect`, `consumer`, `operator`) and add domain charters
(security, accessibility, privacy, cost, i18n) when the stakes call for them.

Each charter names a **responsibility**, an **explicit non-scope**, and the
**evidence** it may use. The non-scope is what stops four lenses from all
commenting on naming. Do not run a lens whose charter has no bearing on the
artifact; an idle lens produces filler.

### 3. Dispatch

One `review-lens` worker per charter, each with a self-contained brief: the
frame, its charter, the artifact location, and the finding contract. Send them
in one batch.

Workers are **independent**. A worker must not see another worker's findings —
shared output anchors the later reviewer and destroys the corroboration signal
that adjudication depends on. Independence is the whole reason to run more than
one lens.

Workers are read-only. They return findings; the caller persists them.

### 4. Adjudicate

```bash
python3 "${CONTEXT_KIT_DEEP_REVIEW_ROOT}/scripts/adjudicate-findings.py" \
  --frame "<work dir>/frame.json" \
  --findings-dir "<work dir>/findings" \
  --out-dir "<work dir>/report"
```

Adjudication validates each finding against the contract, fingerprints findings
by type and location, merges corroborations into one finding carrying every
lens that raised it, flags contradictory recommendations at the same location
as unresolved tradeoffs, and emits the review ledger. It exits nonzero when a
lens report is malformed or a charter produced no report — a missing lens is
reported, never silently dropped. See `references/adjudication.md`.

### 5. Route

- `defect` findings → `verify` for a verdict before anyone acts on them.
- `risk` findings are queued for triage, not routed. Decide here whether each
  trigger is *observable*: only then can `runtime-evidence` settle it, and
  only after static verification leaves it unresolved. A maintenance or
  adoption risk has a real trigger that no command can reproduce.
- Unresolved tradeoffs → the human who owns the decision. Do not pick a winner.
- `question` findings → answer them, then re-run only the affected lens.

### 6. Report

Report findings **and** the ledger together, including what was not reviewed. A
findings list alone invites the reader to assume the whole artifact was read and
that silence means approval.

## Practices

1. **Falsify or downgrade.** An adversarial finding must exhibit a concrete
   failing input, sequence, or state. If it cannot, it is a `risk`, not a
   `defect`. This is the line between red-teaming and nitpicking.
2. **Corroboration merges, never multiplies.** Two lenses reaching the same
   finding is evidence it matters — it raises confidence on one finding, it does
   not create two.
3. **Conflict is a tradeoff, not a defect.** When the architect wants an
   abstraction the consumer calls overhead, surface both and name the decision.
   Silently resolving it hides the most valuable output of a panel.
4. **Consequence or it is not a finding.** State what goes wrong, for whom, and
   under what conditions. "Violates the single responsibility principle" is a
   citation, not a consequence.
5. **Every finding names a resolution.** A finding with no path to resolution is
   a complaint. "Unclear how to fix" is acceptable only as a `question`.
6. **Rank against the stakes, not against other findings.** Severity is a
   property of consequence, not a distribution to be filled out.
7. **Review the artifact, not the author.** Findings cite locations in the work,
   never intent or competence.

## Composition

- **`verify`** — owns truth. Every `defect` becomes a claim there, and the
  verdict comes back into the report. Deep review never grades its own defects.
- **`plan-execute`** — supplies the fan-out. Lens reading is mechanical; pin
  workers to a cheaper model and keep the strong model for framing and
  adjudication.
- **`runtime-evidence`** — settles an observable `risk` that static reading
  cannot, through its allowlisted-ID path.
- **`corpus-review`** — when the artifact is too large for one worker context,
  shard it there first and review the shards. Coverage and judgment compose.
- **`memory`** — recalls settled constraints and prior review decisions so the
  panel does not relitigate them, and captures the tradeoffs this review closes.
- **`code-search`** / **`retrieval-strategy`** — lenses need context beyond the
  diff. Locate callers, precedents, and history before judging a change.
- **`change-impact`** — when a lens claims wide blast radius, that analysis is
  its own read-only pass rather than a guess inside a finding.

## References

- **`references/lens-charters.md`** — the default charters, their non-scopes,
  and how to write a domain charter.
- **`references/finding-contract.md`** — the finding schema, severity
  definition, and required fields.
- **`references/adjudication.md`** — fingerprinting, corroboration merging,
  conflict detection, and the review ledger.

## Portability

GitHub Copilot CLI installs this plugin directly:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install deep-review@context-kit
```

APM installs the same plugin, and its manifest also pulls `verify` and
`plan-execute`:

```bash
apm marketplace add mbeacom/context-kit
apm install deep-review@context-kit
```

Claude Code installs it via `/plugin`:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install deep-review@context-kit
```

Set `CONTEXT_KIT_DEEP_REVIEW_ROOT` to the installed plugin directory for the
script paths above. In Claude Code, `${CLAUDE_PLUGIN_ROOT}` resolves to the same
location.
