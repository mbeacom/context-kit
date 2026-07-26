# Shard Dispatch

A shard is a bounded batch of units assigned to one worker. It exists so review
fits in a context window; it must not leak into anything the reader sees.

## Budgets

Bound both dimensions:

- `--max-bytes` — total decoded size the worker will read. Set it well under the
  worker's context so the brief, the taxonomy, and the findings all fit.
- `--max-units` — count ceiling, so a shard of many tiny units stays legible.

A unit larger than `--max-bytes` gets its own shard and is reported as
`oversized`. That is a signal to subdivide it in the inventory step
(`--max-unit-bytes`), not something the planner should silently truncate.

Units are packed in inventory order. Adjacent order usually reflects directory
structure, which keeps related material together and makes a worker's brief
coherent. Do not reorder for tighter packing — determinism is worth more than a
few percent of fill.

## Shard digest

Each shard records `digest`, a SHA-256 over its member unit hashes in order.
The digest is the resumption key and the drift detector:

- A findings file whose recorded digest matches is reused; the shard is skipped.
- A digest mismatch means the corpus changed under the review. The shard is
  re-dispatched and the change is reported — never merged silently.

## Schema

```json
{
  "schema": "context-kit/corpus-shards-v1",
  "generated_at": "2026-07-25T12:00:00+00:00",
  "inventory_sha256": "…",
  "budget": { "max_bytes": 200000, "max_units": 25 },
  "totals": { "shards": 32, "units": 631, "bytes": 18102411, "oversized": 1 },
  "shards": [
    {
      "id": "s001",
      "digest": "…",
      "bytes": 198442,
      "oversized": false,
      "units": [
        {
          "id": "u0001",
          "path": "docs/runbooks/rotate-keys.md",
          "sha256": "…",
          "bytes": 4821,
          "range": null
        }
      ]
    }
  ]
}
```

`inventory_sha256` binds the plan to the inventory it was built from — a digest
over the inventory's `scope` and `units`, not its raw bytes. An aggregation run
that sees different content or different scope rules refuses to proceed rather
than computing coverage against a denominator that no longer applies. Re-running
the inventory over an unchanged corpus reproduces the same digest, so resuming
never requires keeping the original file byte-for-byte.

## Worker brief

Every brief is self-contained. A worker does not inherit the caller's context,
and it must not need to ask a follow-up question to start.

Include:

1. The review question, verbatim from the frame.
2. The finding taxonomy and what makes a finding significant.
3. The shard's unit list — path, range, and inspectability for each.
4. The citation rule: cite `<unit path>` and a location inside it, never the
   shard id.
5. The output path for the shard's findings file.
6. The instruction to report its own coverage — which units it read in full,
   which it could not, and why.

Do not include the whole inventory. A worker that can see the rest of the corpus
will wander outside its shard, which breaks the coverage arithmetic.

## Concurrency

Dispatch independent workers in one batch. Start with a small bound on an
unfamiliar corpus — run a single shard end to end and read its findings before
committing the rest. A taxonomy problem found on shard 1 is cheap; the same
problem found after 32 shards is a full re-run.

Raise concurrency only after the first shard's output is usable. Bound it so
extraction tools, file handles, and any rate-limited model stay within their
limits.

## Resumability

The findings directory is the durable state. The inventory and shard plan are
reproducible from the corpus — re-running `inventory-corpus.py` and
`plan-shards.py` with the same scope rules and budgets yields the same digests,
so a resumed run matches its existing findings files:

- One findings file per shard, named for the shard id.
- Each file records the shard id and digest it was produced from.
- On resume, a shard with a matching findings file is skipped; a shard with a
  missing, malformed, or stale-digest file is re-dispatched.
- A shard that errors is recorded as `failed` with its reason and left for the
  next run. Failure is retryable state, not a silent hole.

This makes an interrupted run cheap to continue and makes a partial run honest:
the ledger reports the unfinished shards instead of averaging over them.

## Findings file shape

Workers write Markdown with a small machine-readable header so aggregation does
not have to guess:

```markdown
---
schema: context-kit/corpus-findings-v1
shard: s001
digest: "…"
units_reviewed: ["u0001", "u0002"]
units_uninspectable: [{ "id": "u0003", "reason": "image-only, no text layer" }]
---

## Findings

- [TAG] [significance: high] `docs/runbooks/rotate-keys.md:118`
  **Observation:** …
  **Why it matters:** …

## Gaps observed

- …
```

`units_reviewed` and `units_uninspectable` must together account for every unit
in the shard. Aggregation treats any unaccounted unit as `pending`, which keeps
a worker that quietly skipped material from being counted as complete.
