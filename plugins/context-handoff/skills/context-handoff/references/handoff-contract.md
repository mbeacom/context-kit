# Handoff Contract

Use schema identifier `context-kit/handoff-v1`. Encode the artifact as UTF-8
Markdown with a flat YAML frontmatter block and the required level-two sections
in the exact order below.

## Limits

- Maximum encoded size: 32 KiB.
- Maximum line count: 300.
- Maximum top-level list items per required section: 25.
- Maximum one artifact per task handoff path.
- No transcript dumps, hidden reasoning, generated embeddings, or binary data.

## Required frontmatter

| Field | Meaning |
| --- | --- |
| `schema` | Exact value `context-kit/handoff-v1`. |
| `generated_at` | ISO 8601 timestamp with timezone. |
| `repository` | Stable normalized repository identity, preferably `owner/name`. |
| `worktree` | Worktree path at compile time; provenance only, not an identity key. |
| `branch` | Branch containing the task state. |
| `head` | Commit checked out when compiled. |
| `base_ref` | Intended comparison/integration base, such as `main`. |
| `base_commit` | `merge-base(head, base_ref)` at compile time. |
| `worktree_state` | Exact value `clean` or `dirty`. |

Use plain scalar values. Quote a value only when YAML requires it. Do not add
nested frontmatter mappings.

## Required sections

1. `## Scope` — task objective and explicit boundaries.
2. `## Verified Facts` — atomic claims with evidence and verify verdict.
3. `## Decisions` — choices made, rationale, and constraints.
4. `## Changed Files` — repository-relative path, status, and purpose.
5. `## Completed Work` — outcomes already delivered, not intentions.
6. `## Unresolved Items` — open questions, blockers, risks, or `- None.`.
7. `## Next Steps` — ordered, executable actions for the next session.
8. `## Validation State` — command or observation, result, and relevant scope.
9. `## Provenance and Freshness` — restate comparison anchors and explain when
   the artifact must be revalidated.

Keep all required sections, even when empty. Write `- None.` for an empty
section. Do not replace verified facts with assumptions. Put an unverified but
important statement under unresolved items and state what would verify it.

## Verified fact format

Use the `verify` plugin's verdict taxonomy and its evidence forms. `verify` owns
both; do not widen them here.

```text
- confirmed — <atomic claim> — evidence (<path:line, or observation source + artifact pointer>) — <note>
- dubious — <atomic claim> — evidence (<path:line, observation source + artifact pointer, or none>) — <caveat>
- refuted — <atomic claim> — evidence (<path:line, or observation source + artifact pointer>) — <contradiction>
- unable-to-check — <atomic claim> — evidence (none, or observation source + artifact pointer when a collection was attempted and proved inconclusive) — <what would settle it>
```

The observation source is `command-id=<allowlist key>` or
`tool=<approved tool>@<target>`, per `verify`'s evidence forms.

Use the observation form only for a fact whose result was actually observed, such
as a recorded `runtime-evidence` collection. A statically verified fact keeps its
`path:line`. See `verify-before-trust/references/verdicts.md` for the full rules.

Only `confirmed` facts should normally drive resume behavior without another
check, and only when provenance is still current.

## Validation state format

Record reproducible checks:

```text
- passed — `python3 -m unittest discover ...` — 5 tests passed.
- failed — `tool check` — failure summary; not resolved.
- not run — browser smoke test — runtime unavailable.
```

Do not summarize a command as passed when only a narrower proxy ran.
