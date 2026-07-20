---
name: memory-workflows
description: "Use when capturing, recalling, reviewing, or consolidating durable project memory across sessions, especially prior decisions, constraints, procedures, and episodes that must retain source provenance and freshness."
license: MIT
compatibility: "Python 3 is required for the bundled validator/provider adapter. MemPalace is optional and must be installed separately for provider-backed recall."
metadata:
  author: Mark Beacom
  version: "0.2.0"
allowed-tools: Read Grep Glob Write Bash(python3:*) Bash(mempalace:*) Bash(git:*)
---

# Memory Workflows

Use durable memory for **reviewed information that should outlive one task**, not
as a transcript dump or a replacement for current repository evidence.

## Choose the right continuity layer

| Need | Use |
| --- | --- |
| Current task state and next action | `context-handoff` |
| Meaning-based search across a document corpus | `local-rag` |
| Prior decisions, constraints, procedures, or bounded episodes | durable memory |
| Exact current implementation or history | lexical/code-intelligence/Git |

MemPalace is an optional external provider for verbatim storage and recall.
`context-kit` keeps the memory contract, review policy, and verification gates
provider-neutral.

## Capture

1. Capture only an atomic fact, decision, procedure, constraint, or bounded
   episode that is likely to matter later.
2. Preserve immutable evidence. A concise primary memory and cue anchors are
   derived retrieval aids, never replacements for the source.
3. Bind project memories to repository, branch, HEAD, observation time, source,
   and SHA-256 source hash.
4. Mark new records `review: proposed`. Promote them to `accepted` only after
   checking the evidence with the append-only `record-state` operation; never
   edit an already captured artifact.
5. Validate with `scripts/memory-provider.py validate`, then persist with
   `capture`. Provider archival is optional.

Do not silently harvest whole transcripts, secrets, unverified speculation,
temporary debugging noise, or information whose retention has not been approved.

## Recall

1. Scope recall to an explicit project. Never query a global personal store by
   accident.
2. Search primary memories and cue language. Treat results as candidate leads.
3. Open the cited source and compare its hash, repository anchors, and current
   code state.
4. Apply `verify-before-trust` to stale, consequential, or conflicting claims.
5. Report which parts are current, stale, superseded, or unable to check.

Use the composition **recall then pin**: memory locates the likely decision or
episode; repository/filesystem evidence establishes what is true now.

## Review and consolidate

Run review before relying on old records. Consolidation is propose-only:

- exact duplicate evidence may be deduplicated;
- a changed abstraction becomes a new record with a `supersedes` edge;
- evidence remains immutable;
- conflicts stay visible until a reviewer accepts one account;
- proposed, stale, superseded, revoked, and rejected records remain auditable
  but do not drive active recall or provider indexing.

Never destructively rewrite the only evidence for a remembered claim.

## Optional lifecycle queue

Claude hooks ship inert. When explicitly enabled, they queue lifecycle payloads
under the project-isolated memory home for manual review:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

Hooks never create reviewed memory records or mutate a provider palace. Review a
queued payload, create a `memory-v1` artifact, run explicit `capture`, and then
run `sync-provider --apply` when provider recall should change. GitHub Copilot
and APM do not run Claude hooks.

## Resources

- **`references/memory-contract.md`** — record schema and evidence rules.
- **`references/provider-mempalace.md`** — provider setup, isolation, and CLI.
- **`references/provider-qualification.md`** — provider qualification criteria
  and the current decision table for local records, MemPalace, and Memora.
- **`references/retrieval-and-review.md`** — recall, freshness, cues, and
  consolidation.
- **`references/automation.md`** — opt-in hook behavior and host boundaries.
- **`templates/memory.md`** — canonical record template.
- **`../../scripts/memory-provider.py`** — deterministic validator and adapter.
