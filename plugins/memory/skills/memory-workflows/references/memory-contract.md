# Durable Memory Contract

`context-kit/memory-v1` is a UTF-8 Markdown artifact with flat YAML frontmatter
and five required level-two sections. The bundled validator limits a record to
32 KiB and 220 lines. Once captured, its bytes are immutable.

## Three-layer record

1. **Evidence** — immutable source material or a precise pointer to it.
2. **Primary memory** — one concise canonical abstraction used for retrieval.
3. **Cue anchors** — zero to three short entity-plus-aspect alternate keys.

This separation borrows Memora's useful distinction between retained value,
primary index, and cue links while strengthening provenance for engineering
work. Generated summaries and cues are disposable derived indexes. Evidence is
not.

## Required frontmatter

| Field | Rule |
| --- | --- |
| `schema` | Exact value `context-kit/memory-v1`. |
| `id` | Stable lowercase identifier using letters, numbers, `.`, `_`, or `-`. |
| `type` | `fact`, `decision`, `procedure`, `constraint`, or `episode`. |
| `scope` | Exact value `project`; v1 has no global personal namespace. |
| `repository` | Stable `owner/name` identity matching the configured project. |
| `branch` | Observation branch for project memory. |
| `head` | Observation commit for project memory. |
| `observed_at` | ISO 8601 timestamp with timezone for the source event. |
| `captured_at` | ISO 8601 timestamp with timezone for record creation. |
| `freshness` | `current`, `stale`, `superseded`, or `revoked`. |
| `review` | `proposed`, `accepted`, or `rejected`. |
| `source` | Source path or stable evidence identifier. |
| `source_hash` | Lowercase SHA-256 of the source bytes. |

Project records require a valid `owner/name`, Git branch, and 7–64 character
hexadecimal commit, and the repository must exactly match the configured memory
project. If those anchors are unavailable, retain the item as unresolved context
rather than claiming a durable project memory.

## Append-only state ledger

The frontmatter `review` and `freshness` values are the immutable initial state,
not fields to edit after capture. Later changes use:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  record-state retry-policy --review accepted \
  --reason "Compared the saved evidence with the current retry policy."
```

State events are write-once JSON files under
`${CONTEXT_KIT_MEMORY_HOME}/states/<project-key>/<record-id>/`. Each binds the
exact SHA-256 of the record, exact project identity/key, timestamp, prior and
effective review/freshness state, and a non-empty reason. The adapter rejects
events for missing records, mismatched hashes/projects, invalid transition
chains, and terminal freshness transitions.

New events have a zero-padded per-record sequence prefix assigned under the
record lock, so replay order does not depend on the wall clock. Older
timestamp-named events remain readable in deterministic filename order, but
must be migrated before appending a new sequenced event. Locks record PID,
token, and acquisition time. On POSIX, only a confirmed dead PID is reclaimed;
on other platforms process liveness is not portable, so only a conservative age
timeout can reclaim an owner lock and young or unverifiable locks are refused.

With no event, effective state is the immutable frontmatter. Active recall and
provider eligibility require **both** `review: accepted` and
`freshness: current`; all other records remain available to review and explicit
local audit search (`search --include-inactive`).

## Required sections

1. `## Primary Memory` — at most 600 characters.
2. `## Cue Anchors` — at most three bullets; `- None.` is valid.
3. `## Evidence` — non-empty source pointer and relevance.
4. `## Supersedes` — prior IDs or `- None.`.
5. `## Review Notes` — review rationale and conflict/freshness notes.

## Capture threshold

Capture an item only when it is:

- useful beyond the current task;
- atomic enough to verify and update;
- supported by durable evidence;
- safe and appropriate to retain;
- scoped so it cannot leak across unrelated projects.

Do not capture hidden reasoning, credentials, raw environment dumps, broad
transcripts by default, or model-generated claims that have not been checked.
