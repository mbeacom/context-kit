---
description: Archive one validated context handoff into project-scoped durable memory.
argument-hint: "[handoff-path]"
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*)
---

Archive a handoff only as an explicit separate action.

1. Resolve `$ARGUMENTS`, then `CONTEXT_KIT_HANDOFF_PATH`, then
   `.context-kit/handoff.md`.
2. Validate it with the `context-handoff` workflow against the current repository.
   Reject repository/branch/base mismatches. Reverify stale claims before
   archival and do not alter the original artifact.
3. Require an explicit `CONTEXT_KIT_MEMORY_PROJECT` matching the intended
   repository scope.
4. Resolve the memory plugin root and run:

   ```bash
   python3 "<memory-root>/scripts/memory-provider.py" \
     archive-handoff "<resolved-handoff>"
   ```

5. Report the exact preserved archive path, saved HEAD, project scope, and
   provider archival state. Handoffs are intentionally provider-skipped:
   they remain local historical evidence rather than entering the active
   accepted/current provider index.

An archived handoff remains historical evidence, not authoritative current task
state. Future resume still uses `context-handoff` freshness validation.
