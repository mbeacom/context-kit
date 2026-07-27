# Inventory Contract

The inventory is the denominator for every coverage claim. It must be
reproducible: the same corpus and the same scope rules produce the same units,
and therefore the same inventory digest.

## What a unit is

A unit is the smallest thing a reviewer can be said to have read in full. For a
file tree that is normally one file. Choose a smaller unit when a single file
would not fit a worker's context — pages of a document, days of a log, records
of an export — and record the sub-range on the unit so citations stay precise.

Never let a unit span two source files. Two files that must be read together are
two units placed in the same shard.

## Identity

Every unit carries `path` **and** `sha256`. The path alone is not identity:

- A re-run detects drift by comparing hashes, so a corpus that changed
  mid-review is reported rather than silently mixed.
- Resumption is safe. A findings file is only reusable when its shard digest —
  derived from member hashes — still matches.
- Duplicate content is visible. Identical hashes at different paths are a real
  finding in most audits.

## Inspectability

`inspectable` records whether the unit's content can be read at all, before any
review happens. It is deliberately conservative and separate from disposition:
inspectability is a property of the unit, disposition is the outcome of a review.

| Signal | Meaning |
| --- | --- |
| `text` | decoded as UTF-8 without loss |
| `text-lossy` | decoded with replacement characters; partially readable |
| `binary` | not decodable as text; needs an extraction tool |
| `empty` | zero bytes |
| `unreadable` | could not be opened — permissions, broken link, I/O error |

A `binary` unit is not a failure. It means extraction has to happen first —
`pdftotext`, `pandoc`, `rga` from the `data-and-docs-search` skill — or the unit
is carried into the ledger as `uninspectable` with the reason recorded.

## Scope rules are data

Include and exclude patterns belong in the inventory, not in shell history. The
script records the patterns it applied and emits excluded units with
`out_of_scope` rather than dropping them. An excluded unit is accountable; a
silently skipped one is indistinguishable from one that was never there.

## Schema

```json
{
  "schema": "context-kit/corpus-inventory-v1",
  "generated_at": "2026-07-25T12:00:00+00:00",
  "root": "/absolute/corpus/root",
  "scope": {
    "include": ["**/*.md"],
    "exclude": ["**/node_modules/**"],
    "follow_symlinks": false
  },
  "errors": [],
  "totals": {
    "units": 640,
    "bytes": 18234112,
    "in_scope_units": 631,
    "out_of_scope_units": 9,
    "by_inspectability": { "text": 612, "binary": 19 }
  },
  "units": [
    {
      "id": "u0001",
      "path": "docs/runbooks/rotate-keys.md",
      "bytes": 4821,
      "sha256": "…",
      "inspectable": "text",
      "in_scope": true,
      "range": null
    }
  ]
}
```

`units` is sorted by `path`, and `id` is assigned in that order, so two runs
over an unchanged corpus produce an identical `units` array.

The inventory **digest** — what `plan-shards.py` records as `inventory_sha256`
and `aggregate-findings.py` re-checks — covers `scope` and `units` only, not the
whole file. `generated_at` and `root` are deliberately excluded so that
re-running the inventory, or moving the corpus, does not invalidate a review
that is already underway. Change the content or the scope rules and the digest
changes; change only when you ran it and it does not.

Excluded units are listed with `in_scope: false`, but they are not opened or
hashed — `sha256` and `inspectable` stay `null`. An excluded unit is
accountable, without the scope rule being defeated by the act of recording it.

`range` is `null` for a whole-file unit, or `{"kind": "lines", "start": 1,
"end": 500}` when a large unit was subdivided. Citations use the unit path plus
its range, never a shard identifier.

## Untraversable directories

`errors` records every directory the walk could not enter, with the reason.
This is not cosmetic. `os.walk` ignores traversal errors by default, so an
unreadable subtree would simply not appear — and a unit that never enters the
denominator cannot be reported as unread. Coverage would then look complete over
a corpus that quietly lost files.

The script exits nonzero when `errors` is non-empty. Fix the permissions,
exclude the subtree explicitly so it is accounted for as `out_of_scope`, or pass
`--allow-unreadable` to accept a known-incomplete denominator. In the last case
the ledger reports the errors and refuses every `not-found` absence verdict,
because material nobody could enumerate could hold the expected item.

## Invocation

```bash
python3 "${CONTEXT_KIT_CORPUS_REVIEW_ROOT}/scripts/inventory-corpus.py" \
  --root "<corpus root>" \
  --out "<work dir>/inventory.json" \
  --include '**/*.md' \
  --exclude '**/node_modules/**' \
  --max-unit-bytes 65536
```

Inside Claude Code plugin components, use
`${CLAUDE_PLUGIN_ROOT}/scripts/inventory-corpus.py` when the neutral plugin root
variable is not set. Prefer `CONTEXT_KIT_*` variables in portable instructions.

The script reads only. It never follows symlinks unless asked, and refuses to
write its output inside the corpus root so a re-run cannot enumerate its own
artifacts. `plan-shards.py` and `aggregate-findings.py` apply the same
containment rule, reading the corpus root from the inventory.
