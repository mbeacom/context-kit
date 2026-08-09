# corpus-review

Exhaustive review for a corpus too large to read in one context. Retrieval finds
relevant material; this plugin reads *all* of it and reports what was actually
inspected. It enumerates units, shards them under a bounded budget, dispatches
resumable workers that cite original locations, and aggregates the results into
a coverage ledger that separates a real gap from an undecidable one.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install corpus-review@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install corpus-review@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install corpus-review@context-kit
```

The plugin depends on `plan-execute` for worker fan-out and `verify` for the
evidence discipline; `verify` already pulls the `retrieval-core` spine. The
bundled scripts need Python 3 and use only the standard library. Extracting
non-text units (PDF, Office, archives) relies on the separately installed tools
described by `code-search`'s `data-and-docs-search` skill.

## Components

| Component | Purpose |
| --- | --- |
| **`corpus-review`** skill | The frame → inventory → shard → dispatch → aggregate → report pipeline, the disposition vocabulary, and the absence rule. |
| **`corpus-reviewer`** agent | Reads one shard against the supplied review question and reports findings plus its own honest coverage. Read-only and shard-scoped. |
| **`/review-corpus`** command | Runs the pipeline end to end over a corpus root. |
| **`inventory-corpus.py`** script | Enumerates the corpus into deterministic, hashed units with an inspectability signal. |
| **`plan-shards.py`** script | Packs units into bounded shards with digests that make resumption safe. |
| **`aggregate-findings.py`** script | Merges shard findings into a coverage ledger and refuses to call an incomplete run complete. |

## Why this is not retrieval

| Retrieval | Corpus review |
| --- | --- |
| Success is relevant hits | Success is every unit accounted for |
| Recall is best-effort | Coverage is stated and provable |
| Returns ranked candidates | Returns a disposition per unit |
| Absence is not measured | Absence is a first-class, two-valued output |

Reach for retrieval first — `retrieval-strategy`, `code-search`, `indexkit`.
Escalate here only when someone will act on what *was not* found.

## Quick start

```bash
ROOT="${CONTEXT_KIT_CORPUS_REVIEW_ROOT:-plugins/corpus-review}"

python3 "$ROOT/scripts/inventory-corpus.py" \
  --root ./corpus --out ./work/inventory.json \
  --include '**/*.md' --exclude '**/node_modules/**'

python3 "$ROOT/scripts/plan-shards.py" \
  --inventory ./work/inventory.json --out ./work/shards.json \
  --max-bytes 200000 --max-units 25

# dispatch one corpus-reviewer per shard -> ./work/findings/<shard>.md

python3 "$ROOT/scripts/aggregate-findings.py" \
  --inventory ./work/inventory.json --shards ./work/shards.json \
  --findings-dir ./work/findings --out-dir ./work/report \
  --expected ./work/expected.txt
```

Aggregation exits nonzero while any unit is `pending` or `failed`, so an
interrupted run cannot be reported as a finished one.

## The two rules that matter

**Coverage is measured, never assumed.** Every unit ends as `reviewed`,
`partial`, `uninspectable`, `out_of_scope`, `failed`, or `pending`, and the
dispositions sum to the inventory. A unit nobody claimed stays `pending`, so a
worker's silence never reads as coverage.

**`indeterminate` outranks `not-found`.** An expected item that no worker found
is only a real gap when every unit that could contain it was actually read. While
any unit is uninspectable, partially read, failed, or pending, absence is
undecidable and is reported as such. Downgrading that — treating an unread unit as read and empty —
is how automated review causes harm: the phantom gap gets acted on as fact.

This is `verify`'s `unable-to-check` verdict raised from one claim to a whole
corpus.

## Development

```bash
python3 -m unittest discover -s plugins/corpus-review/tests -p 'test_*.py'
```

The tests are hermetic: no network, no model, temporary directories only.
