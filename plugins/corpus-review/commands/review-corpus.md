---
description: Review an entire corpus with bounded shards and a provable coverage ledger.
argument-hint: [corpus-root]
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3:*)
---

Run an exhaustive review over the corpus at `$ARGUMENTS`, or ask for the root
when the argument is empty.

Use this when the deliverable requires coverage. If a representative answer is
enough and nobody will act on the absence of a hit, stop and use retrieval
instead — say so rather than running a full review.

## 1. Frame

Collect and restate before enumerating anything:

- The **review question** — what every unit is being read for.
- **Scope rules** — include and exclude patterns.
- The **finding taxonomy** — allowed tags and what makes a finding significant.
- An **expected inventory**, if one exists. Without it, absence verdicts are
  unavailable and the report must say so.
- A **work directory** outside the corpus root for inventory, shards, findings,
  and the report.

If the review question is missing, stop and ask. Do not infer it from the
corpus.

## 2. Inventory

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inventory-corpus.py" \
  --root "<corpus root>" --out "<work>/inventory.json" \
  --include '<pattern>' --exclude '<pattern>'
```

Read the totals. If a large share of units is `binary`, decide with the user
whether to extract them first or carry them as `uninspectable` limitations.

## 3. Plan shards

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan-shards.py" \
  --inventory "<work>/inventory.json" --out "<work>/shards.json" \
  --max-bytes <budget> --max-units <count>
```

Report any `oversized` shard. Subdivide those units with `--max-unit-bytes` at
the inventory step rather than letting a worker truncate them.

## 4. Dispatch

Run **one shard first** and read its findings before committing the rest. A
taxonomy problem found on shard 1 is cheap.

Then dispatch the remaining shards to `corpus-reviewer` workers in batched
parallel calls. Give each worker a self-contained brief: the review question,
the taxonomy, its unit list with paths and inspectability, the citation rule,
and its output path under `<work>/findings/`. Do not give a worker the full
inventory.

Skip any shard whose findings file already records a matching digest. Re-dispatch
shards whose file is missing, malformed, or stale.

## 5. Aggregate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-findings.py" \
  --inventory "<work>/inventory.json" --shards "<work>/shards.json" \
  --findings-dir "<work>/findings" --out-dir "<work>/report"
```

A nonzero exit means the run is incomplete. Re-dispatch the `pending` and
`failed` shards and rerun. Do not report an incomplete run as finished; if the
user chooses to stop early, report the ledger as incomplete and name what is
unaccounted for.

## 6. Report

Report findings and coverage together:

- Findings by tag, with the top items cited by unit path and location.
- Coverage by unit and by byte, with the denominator stated.
- `uninspectable` units grouped by reason, routed to remediation.
- Absence verdicts, `not-found` separated from `indeterminate` — and never
  present an `indeterminate` item as missing.
- Residual risk: what the scope rules excluded and what remains unaccounted for.

Use `verify` on any consequential finding before it is acted on. If the review
spans sessions, use `context-handoff` to carry the frame, the work directory,
and the ledger.
