# Resume Safety

Validate structure first, then compare the artifact's saved context with the
current repository context. Treat the categories differently:

| Difference | Classification | Resume behavior |
| --- | --- | --- |
| Malformed schema, missing section, unresolved template placeholder | Invalid | Stop. Repair or regenerate the artifact. |
| Repository identity differs | Mismatch | Reject as authoritative task state. |
| Branch differs | Mismatch | Reject unless the operator intentionally switches to the saved branch and reruns validation. |
| Base ref differs | Mismatch | Reject until the intended integration base is resolved explicitly. |
| HEAD differs | Stale | Flag prominently and reverify affected claims. |
| Merge-base commit differs | Stale | Flag base movement and recheck assumptions made against the old base. |
| Worktree clean/dirty state differs | Stale | Reinventory changed files and validation state. |
| Worktree path differs, identity anchors match | Informational | Expected across worktrees/hosts; do not reject for path alone. |

## Resume sequence

1. Run the deterministic validator.
2. Stop on exit `1` (invalid) or `2` (mismatch).
3. On exit `3` (stale), show every stale field before using content.
4. Reverify saved confirmed facts, changed files, completed work, and validation
   results against current primary evidence.
5. Downgrade or discard any claim that no longer matches.
6. Select the first next step only after the trust boundary is clear.

Avoid "close enough" branch or repository matching. Normalize common Git remote
forms to a stable `owner/name` identity while compiling, then compare exact
normalized identities.

Do not use the artifact as an automatic RAG or memory source. The separate
`memory` plugin may archive it only after an explicit request and this freshness
check. Archived copies remain historical evidence and retain an explicit
retention/deletion policy; they do not become authoritative resume state.
