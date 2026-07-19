---
description: Validate and safely resume a bounded task handoff.
argument-hint: [artifact-path]
allowed-tools: Read, Grep, Glob, Task, Bash(git:*), Bash(python3:*)
---

Resume task state from a `context-kit/handoff-v1` artifact without silently
trusting stale context.

Resolve the source in this order:

1. `$ARGUMENTS` when non-empty.
2. `CONTEXT_KIT_HANDOFF_PATH` when set.
3. `.context-kit/handoff.md` under the repository root.

Resolve a relative path from the repository root. Read the artifact, then gather
the current normalized repository identity, branch, HEAD, intended base ref,
merge-base commit, and clean/dirty worktree state with read-only `git` commands.
Derive the intended base independently from current session or repository
configuration; do not copy the saved `base_ref` into the current-value argument
merely to make validation pass. Then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-handoff.py" "<resolved-path>" \
  --current-repository "<repository>" \
  --current-branch "<branch>" \
  --current-head "<head>" \
  --current-base-ref "<base-ref>" \
  --current-base-commit "<merge-base>" \
  --current-worktree-state "<clean-or-dirty>"
```

Interpret the exit status strictly:

- `0`: structure and supplied context anchors match.
- `1`: artifact is malformed; stop and report the structural errors.
- `2`: repository, branch, or base ref mismatches; reject the artifact as
  authoritative task state and stop.
- `3`: HEAD, merge-base, or worktree state is stale; show every difference
  before proceeding.

For stale artifacts, use the `verify-before-trust` skill or `verifier` subagent
to recheck saved verified facts, changed-file claims, completed-work claims, and
validation state against the current repository. Downgrade or discard claims
that no longer hold.

Return a compact resume brief containing current scope, trusted facts,
invalidated or uncertain claims, unresolved items, and the first safe next step.
Do not modify the artifact, switch branches, execute its next steps, or ingest
it into RAG or memory unless the user separately requests that action. Explicit
memory archival must occur only after this freshness check and remains historical
evidence rather than current task authority.
