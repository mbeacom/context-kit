---
description: Compile, write, and validate a bounded verified task handoff.
argument-hint: [artifact-path]
allowed-tools: Read, Grep, Glob, Write, Task, Bash(git:*), Bash(python3:*)
---

Write a `context-kit/handoff-v1` artifact for the active repository task.
Manual command execution is authoritative; do not install or simulate lifecycle
hooks.

Resolve the destination in this order:

1. `$ARGUMENTS` when non-empty.
2. `CONTEXT_KIT_HANDOFF_PATH` when set.
3. `.context-kit/handoff.md` under the repository root.

Resolve a relative path from the repository root. Then:

1. Gather repository identity, worktree path, branch, HEAD, worktree status, and
   intended base ref with read-only `git` commands. Normalize the origin remote
   to a stable repository identity. Determine `base_commit` with `git merge-base
   HEAD <base_ref>`. If the base ref cannot be determined unambiguously, stop and
   request it rather than inventing one.
2. Gather the current task objective, scope boundaries, changed-file inventory,
   completed outcomes, decisions, unresolved items, proposed next steps, and
   exact validation commands/results from this session.
3. Use the `verify-before-trust` skill or `verifier` subagent to check claims
   that will affect the next session.
4. Invoke the `handoff-compiler` subagent with all gathered state and
   provenance. The compiler is read-only and must return only bounded structured
   Markdown.
5. Persist the returned Markdown at the resolved destination. Create only the
   necessary parent directory.
6. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-handoff.py" "<resolved-path>"
   ```

7. If validation fails, repair the artifact and rerun validation. Do not report
   success while an invalid artifact remains.

Report the repository-relative artifact path, saved HEAD, base ref, and whether
the saved worktree state was clean or dirty. Do not ingest the artifact into
RAG or any long-term memory system.
