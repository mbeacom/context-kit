# Retrieval and Review

## Recall then pin

Use durable memory when the question asks about a prior decision, constraint,
procedure, preference, or episode and the exact wording/location is unknown.

1. Scope to the explicit project.
2. Query with the user's intent plus likely entity/aspect terms.
3. Inspect the primary result and any cue-mediated alternatives.
4. Open the cited source.
5. Compare repository, branch, HEAD, timestamp, and source hash.
6. Verify the current claim with repository or runtime evidence.

Memory answers **where to look**. Current evidence answers **what is true now**.

## Retrieval signals

Memora's primary/cue separation and weighted rank fusion are useful design
patterns:

- primary memories should outrank cue-only matches;
- cue anchors improve alternate-phrasing recall;
- lexical and semantic signals should be fused rather than substituted;
- recency may break ties but must not erase provenance or validity.

`local-rag --hybrid` applies deterministic semantic plus lexical fusion for
document corpora. MemPalace provides its own hybrid retrieval for durable
memory. Do not merge scores from unrelated stores without preserving their
source labels.

## Freshness

| State | Meaning | Default action |
| --- | --- | --- |
| `current` | Source and anchors still match. | May inform work after evidence is opened. |
| `stale` | Source hash or repository anchors changed. | Reverify before use. |
| `superseded` | A reviewed replacement exists. | Follow the edge; retain for history. |
| `revoked` | Record must not drive behavior. | Exclude from active recall. |

Consequential claims include security, privacy, production operations,
compatibility, migrations, and user-visible behavior. Always run
`verify-before-trust` for these, even when a record says `current`.

## Consolidation proposals

Consolidation must be reviewable:

1. Detect exact duplicate evidence deterministically.
2. Compare only memories with compatible project, type, and entity scope.
3. Show old and proposed primary memories side by side.
4. Cite every supporting and conflicting evidence item.
5. Accept by creating a new record and adding `supersedes` links.
6. Keep old evidence and rejected alternatives.

Never let an LLM silently delete or rewrite the only record of a decision.
