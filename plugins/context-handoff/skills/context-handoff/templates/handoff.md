---
schema: context-kit/handoff-v1
generated_at: "{{ISO_8601_TIMESTAMP}}"
repository: "{{OWNER_OR_REPOSITORY_ID}}"
worktree: "{{WORKTREE_PATH}}"
branch: "{{BRANCH}}"
head: "{{HEAD_COMMIT}}"
base_ref: "{{BASE_REF}}"
base_commit: "{{MERGE_BASE_COMMIT}}"
worktree_state: "{{clean_or_dirty}}"
---

# Context Handoff

## Scope

- {{TASK_OBJECTIVE_AND_BOUNDARIES}}

## Verified Facts

- {{VERIFY_VERDICT}} — {{ATOMIC_CLAIM}} — evidence ({{PATH_LINE_OR_COMMAND}}) — {{NOTE}}

## Decisions

- {{DECISION}} — rationale: {{RATIONALE}} — constraints: {{CONSTRAINTS}}

## Changed Files

- `{{REPOSITORY_RELATIVE_PATH}}` — {{STATUS}} — {{PURPOSE}}

## Completed Work

- {{COMPLETED_OUTCOME}}

## Unresolved Items

- {{OPEN_QUESTION_BLOCKER_OR_RISK}}

## Next Steps

1. {{FIRST_EXECUTABLE_STEP}}

## Validation State

- {{passed_failed_or_not_run}} — `{{COMMAND_OR_OBSERVATION}}` — {{RESULT}}

## Provenance and Freshness

- Compiled from `{{REPOSITORY}}` on `{{BRANCH}}` at `{{HEAD_COMMIT}}`.
- Compared against `{{BASE_REF}}` at merge-base `{{MERGE_BASE_COMMIT}}`.
- Worktree was `{{clean_or_dirty}}`; revalidate if HEAD, base, or worktree state changes.
