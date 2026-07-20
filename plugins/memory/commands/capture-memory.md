---
description: Capture one reviewed durable memory with evidence and provenance.
argument-hint: "[memory-type] [source-path]"
allowed-tools: Read, Grep, Glob, Write, Bash(git:*), Bash(python3:*)
---

Capture one durable memory from `$ARGUMENTS`. Do not harvest a transcript or
capture multiple unrelated claims.

1. Resolve the plugin root from `CONTEXT_KIT_MEMORY_ROOT`, falling back to
   `${CLAUDE_PLUGIN_ROOT}` where available.
2. Gather repository identity, branch, HEAD, current timestamp, source path, and
   SHA-256 source hash. Refuse project capture when repository provenance cannot
   be established.
3. Verify the claim against the source. Use the `verify-before-trust` discipline
   for consequential or disputed claims.
4. Create a `context-kit/memory-v1` artifact from
   `skills/memory-workflows/templates/memory.md`. Use one concise primary memory,
   zero to three cue anchors, verbatim evidence pointers, `review: proposed`, and
   no supersession unless a prior accepted record was actually reviewed.
5. Present the proposed primary memory, cues, evidence, and retention scope for
   review. Do not mark it accepted without explicit evidence review.
6. Run:

   ```bash
   python3 "<memory-root>/scripts/memory-provider.py" validate "<draft>"
   python3 "<memory-root>/scripts/memory-provider.py" capture "<draft>"
   ```

7. Report the persisted artifact path, provider archival state, project scope,
   and effective review/freshness state. Proposed or inactive records are
   locally persisted but must visibly report provider archival as skipped; they
   are never success-shaped archives. After evidence review, use `record-state`
   with a non-empty reason rather than editing the immutable artifact. An
   accepted/current capture is provider-eligible but still pending: run
   `sync-provider --apply` explicitly before provider-backed recall.
