# corpus-review

!!! abstract "Exhaustive review with a provable coverage ledger"
    Reads a corpus too large to fit in one context — a document set, log
    archive, or file tree — and reports what was *actually* inspected. Retrieval
    finds the relevant; this plugin accounts for everything.

`corpus-review` declares `dependencies: ["plan-execute", "verify"]`. It reuses
[`plan-execute`](plan-execute.md)'s cheap-worker fan-out to read shards, and
raises [`verify`](verify.md)'s `unable-to-check` discipline from a single claim
to a whole corpus. `verify` already pulls the
[retrieval spine](retrieval-core.md).

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install corpus-review@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install corpus-review@context-kit   # also deploys plan-execute and verify
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install corpus-review@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`corpus-review`** skill | The frame → inventory → shard → dispatch → aggregate → report pipeline, the disposition vocabulary, and the absence rule. |
| **`corpus-reviewer`** subagent | Reads one shard against the supplied review question and returns findings plus its own coverage. Read-only and shard-scoped — the command persists what it returns. |
| **`/review-corpus`** command | Runs the pipeline end to end over a corpus root. |
| **`inventory-corpus.py`** | Enumerates the corpus into deterministic hashed units with an inspectability signal. |
| **`plan-shards.py`** | Packs units into bounded shards whose digests make resumption safe. |
| **`aggregate-findings.py`** | Merges shard findings into a coverage ledger and refuses to call an incomplete run complete. |

## Review is not retrieval

| | Retrieval | Corpus review |
| --- | --- | --- |
| Success condition | relevant hits surfaced | every unit accounted for |
| Recall | best-effort, unmeasured | stated and provable |
| Output | ranked candidates | a disposition per unit |
| Absence | not measured | first-class and two-valued |

Reach for [`retrieval-strategy`](retrieval-core.md),
[`code-search`](code-search.md), or [`local-rag`](local-rag.md) first. Escalate
here only when someone will act on what was **not** found — ranked hits cannot
establish that nothing was skipped.

[`change-impact`](verify.md) is also not this: it deliberately stops at useful
coverage for a proposed change's blast radius.

## Pipeline

```mermaid
flowchart LR
    F[frame<br/>question + scope + taxonomy] --> I[inventory<br/>hashed units]
    I --> S[shard<br/>bounded budgets]
    S --> D[dispatch<br/>resumable workers]
    D --> A[aggregate<br/>coverage ledger]
    A --> R[report<br/>findings + denominator]
```

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

`--expected` is what makes absence verdicts available; omit it and the ledger
reports them as unavailable rather than guessing.

Claude Code components may use `CLAUDE_PLUGIN_ROOT` as the plugin-root fallback.

## Dispositions

Every unit in the inventory ends in exactly one, and the dispositions sum to the
inventory total:

| Disposition | Assigned when |
| --- | --- |
| `reviewed` | a worker listed the unit as read in full |
| `partial` | reviewed, with a bounded portion recorded as unreadable |
| `uninspectable` | present, but the content could not be read at all |
| `out_of_scope` | excluded by a stated scope rule, not by omission |
| `failed` | its shard errored, or its findings file is malformed |
| `pending` | in a shard with no findings file, or omitted by its worker |

`pending` is the default, so a worker's silence never reads as coverage.
Aggregation exits nonzero while any unit is `pending` or `failed`.

Coverage is reported two ways, and never only the first: unit coverage alone
hides a skipped 4 MB archive among 600 small files, byte coverage alone hides 40
skipped one-line configs.

## Absence: the rule that matters

!!! warning "`indeterminate` outranks `not-found`"
    An expected item nobody found is a real gap (`not-found`) only when every
    unit that could contain it was actually `reviewed`. While any unit is
    `uninspectable`, `partial`, `failed`, or `pending`, absence is undecidable
    and is reported as `indeterminate`.

Downgrading that — treating an unread unit as if it had been read and found
empty — is the characteristic failure of automated review, and the one that
causes real harm: a phantom gap gets acted on as fact. Without an expected
inventory — or with no unit in scope at all — absence verdicts are reported as
unavailable rather than inferred.

Route the buckets differently: `uninspectable` to remediation, `failed` to
retry, `pending` to finishing the run, `indeterminate` to resolving the blocking
units — and only `not-found` to acting on the gap.

## Resumability

The findings directory is the state. Each shard carries a `digest` over its
member content hashes:

- a findings file whose digest matches is reused and the shard is skipped;
- a mismatch means the corpus changed under the review, so the shard is
  re-dispatched and the change is reported rather than merged silently.

The shard plan also records `inventory_sha256`, a digest over the inventory's
scope rules and units rather than its raw bytes. Aggregating against different
content is refused outright, since coverage would otherwise be computed against
the wrong denominator — but simply re-running the inventory reproduces the same
digest, so a resumed review is never invalidated by a fresh timestamp.

## At a glance

- **Requires** Python 3 for the standard-library scripts. Extracting non-text
  units relies on the optional [`data-and-docs-search`](code-search.md) tools.
- **Reads only.** All three scripts refuse to write their output inside the
  corpus root, so a re-run cannot enumerate the review's own artifacts.
- **Hermetic tests:** `python3 -m unittest discover -s plugins/corpus-review/tests -p 'test_*.py'`
