---
description: Recall project memory, then pin and verify the original evidence.
argument-hint: "[query]"
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*)
---

Recall durable memory for `$ARGUMENTS` without treating provider output as proof.

1. Require an explicit `CONTEXT_KIT_MEMORY_PROJECT`. Resolve the plugin root from
   `CONTEXT_KIT_MEMORY_ROOT`, falling back to `${CLAUDE_PLUGIN_ROOT}`.
2. Run `python3 "<memory-root>/scripts/memory-provider.py" doctor`. Stop on
   missing or mis-scoped configuration. `mode: local` is ready for local
   primary-memory and cue search; MemPalace remains optional.
3. Search:

   ```bash
   python3 "<memory-root>/scripts/memory-provider.py" search "$ARGUMENTS" --results 8
   ```

4. Inspect candidate primary memories and cue matches. Local mode returns a JSON
   `records` array; provider mode returns the provider's labeled candidates. Open every source needed
   for the answer and compare source hash plus repository/branch/HEAD anchors.
5. Mark each relied-on claim current, stale, superseded, revoked, conflicting, or
   unable to check. Apply `verify-before-trust` to stale or consequential claims.
6. Return a compact answer with exact current evidence locations. Clearly
   separate remembered context from facts verified in the current repository.
