---
name: memory-workflows
description: "Use when capturing, recalling, reviewing, or consolidating durable project memory across sessions — decisions, constraints, procedures, and episodes that must retain provenance and freshness."
license: MIT
compatibility: "Python 3 is required for the bundled validator/provider adapter. Offline semantic recall uses the bundled indexkit dependency (needs its venv bootstrap plus ollama). MemPalace is optional and installed separately."
metadata:
  author: Mark Beacom
  version: "0.3.0"
allowed-tools: Read Grep Glob Write Bash(python3:*) Bash(mempalace:*) Bash(git:*)
---

# Memory Workflows

Use durable memory for **reviewed information that should outlive one task**, not
as a transcript dump or a replacement for current repository evidence.

## Choose the right continuity layer

| Need | Use |
| --- | --- |
| Current task state and next action | `context-handoff` |
| Meaning-based search across a document corpus | `indexkit` |
| Prior decisions, constraints, procedures, or bounded episodes | durable memory |
| Exact current implementation or history | lexical/code-intelligence/Git |

MemPalace is an optional external provider for verbatim storage and recall.
`context-kit` keeps the memory contract, review policy, and verification gates
provider-neutral.

## Choose a provider

| Provider | Recall | Needs |
| --- | --- | --- |
| `none` | Lexical over primary memories and cue anchors | nothing |
| `rag` | **Offline semantic** (first-party, bundled) | indexkit venv + ollama |
| `mempalace` | Semantic/hybrid | MemPalace installed separately |

Provider-backed recall is active-only and requires explicit reconciliation:
run `sync-provider --apply` after an eligible capture or state change. If a
provider is unreachable, `search` falls back to lexical local search and labels
the result `degraded_from`; it never presents lexical hits as semantic recall.

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

## Mine past sessions (propose, never capture)

`propose-from-session` extracts the human-visible conversation from GitHub
Copilot CLI logs into reviewable **candidates**. It writes nothing by default
and creates no memory records:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" \
  propose-from-session ~/.copilot/session-state          # dry run
```

Only top-level human and assistant turns are retained. Subagent task prompts,
generated skill/agent/command context, tool-nested messages, and model reasoning
are excluded by construction — a subagent prompt is written by the orchestrating
model, so storing it as a user turn would misattribute authorship. Detected
credentials block the write unless `--redact` is passed.

A transcript is not an atomic memory: authoring a `memory-v1` record from a
candidate stays an explicit judgment step. See `references/session-mining.md`.

## Recall

1. Scope recall to an explicit project, or to GitHub Copilot's trusted ephemeral
   session binding. Resolution is `--project` → `CONTEXT_KIT_MEMORY_PROJECT` →
   deprecated `PRODUCTIVITY_SKILLS_MEMORY_PROJECT` →
   `CLAUDE_PLUGIN_OPTION_PROJECT` → matching Copilot session binding. MCP tool
   arguments and prompt content can never select scope.
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

## Prime a session

`wake` builds a bounded, recency-ordered digest of accepted/current records from
the local store, so it is identical under every provider:

```bash
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" wake --format text
```

`audit` sweeps the store for records whose cited source drifted or vanished and
proposes a `record-state` transition for each. It never edits or deletes.

## Optional lifecycle hooks

Recall and capture hooks ship inert behind two independent switches, because
reading and writing are different risks:

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_RECALL_ON_START=true   # SessionStart injects the digest
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true      # boundaries queue for review
```

Both Claude Code and GitHub Copilot CLI load `hooks/hooks.json` and honor
`additionalContext`; APM does not deploy hooks. Capture hooks never create
reviewed records or mutate a provider store — review a queued payload, create a
`memory-v1` artifact, run explicit `capture`, then `sync-provider --apply`.
Tool-level hooks are deliberately not used; see `references/automation.md`.

GitHub Copilot has one bounded routing-only exception: its host-authored
`SessionStart` payload can create a private session-ID-to-project binding after
the payload `sessionId` exactly matches `COPILOT_AGENT_SESSION_ID` and `cwd`
resolves to a Git repository with an `origin`. `SessionEnd` removes it. This
metadata is not a memory record, transcript capture, or provider write. APM and
hosts without both trusted fields still require explicit project configuration.

## Resources

- **`references/memory-contract.md`** — record schema and evidence rules.
- **`references/session-mining.md`** — Copilot session extraction and candidates.
- **`references/mcp-server.md`** — optional MCP surface for non-plugin hosts.
- **`references/provider-rag.md`** — the first-party offline semantic provider.
- **`references/provider-mempalace.md`** — provider setup, isolation, and CLI.
- **`references/provider-qualification.md`** — provider qualification criteria
  and the current decision table for local records, MemPalace, and Memora.
- **`references/retrieval-and-review.md`** — recall, freshness, cues, and
  consolidation.
- **`references/automation.md`** — opt-in hook behavior and host boundaries.
- **`templates/memory.md`** — canonical record template.
- **`../../scripts/memory-provider.py`** — deterministic validator and adapter.
