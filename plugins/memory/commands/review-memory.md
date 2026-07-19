---
description: Review durable memory freshness, conflicts, and consolidation proposals.
argument-hint: "[project-or-record]"
allowed-tools: Read, Grep, Glob, Write, Bash(git:*), Bash(python3:*)
---

Review `$ARGUMENTS` using a propose-only workflow.

1. Require an explicit project scope and resolve the memory plugin root.
2. Run:

   ```bash
   python3 "<memory-root>/scripts/memory-provider.py" review
   ```

3. Open records reported invalid or stale and compare source bytes, repository
   anchors, and current evidence.
4. Identify exact duplicates, conflicts, and plausible successors. Do not merge
   records merely because their embeddings are similar.
5. For each proposed consolidation, show old/new primary memory, cues, all
   supporting/conflicting evidence, and the proposed `supersedes` links.
6. Persist a replacement only after review. Keep prior evidence and records;
   change their freshness state rather than deleting them.
7. Report accepted, rejected, stale, superseded, and unresolved records
   separately.
