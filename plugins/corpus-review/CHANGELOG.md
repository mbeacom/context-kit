# Changelog

## 0.1.0 — 2026-07-25

- Initial release: exhaustive review for a corpus too large to read in one
  context, as a distinct capability from retrieval.
- `corpus-review` skill: the frame → inventory → shard → dispatch → aggregate →
  report pipeline, the unit disposition vocabulary (`reviewed`, `partial`,
  `uninspectable`, `out_of_scope`, `failed`, `pending`), and the absence rule
  that `indeterminate` outranks `not-found` — a partially read, uninspectable,
  failed, or pending unit is never treated as evidence of absence.
- `corpus-reviewer` agent: a bounded per-shard worker with an output contract
  that reports its own coverage and uninspectable units alongside findings.
- `/review-corpus` command for the end-to-end run.
- Standard-library scripts: `inventory-corpus.py` enumerates and hashes units,
  `plan-shards.py` produces a bounded shard plan with original-location anchors
  and a content-derived `inventory_sha256` that survives a re-inventory, and
  `aggregate-findings.py` merges findings into a coverage ledger that refuses to
  report completion while any unit is `pending` or `failed`, and refuses to emit
  an absence verdict when no unit was in scope.
- `findings.md` carries its own coverage caveat, so the standalone artifact
  cannot read as exhaustive when `partial`, `uninspectable`, or warning-bearing
  units mean most of the corpus went unread.
- References for the inventory contract, shard dispatch and resumability, and
  the coverage ledger.
