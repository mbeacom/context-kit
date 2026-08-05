# Changelog

## 0.3.0 — 2026-08-04

- Add an optional stdio MCP server (`mcp/server.py` plus `.mcp.json`) exposing
  `memory_recall`, `memory_capture`, and `memory_review`, so hosts that consume
  skills plus MCP rather than Claude plugins can use durable memory. Standard
  library only, no daemon, no Claude hooks. It shells out to
  `memory-provider.py` with exact argv so the CLI and MCP paths cannot drift.
- The MCP surface can propose memory but **cannot activate it**: `capture`
  derives initial state from frontmatter, so the server refuses any record that
  is not `review: proposed`. `sync-provider`, `record-state` promotion, backup
  pruning, session mining, and destructive operations are not exposed.
- Add `propose-from-session`, which extracts the human-visible conversation
  from GitHub Copilot CLI logs into reviewable
  `context-kit/memory-candidate-v1` candidates. It proposes rather than
  captures: a transcript is not an atomic memory, so authoring a record stays
  an explicit judgment step and nothing mined can enter active recall on its
  own. Dry run is the default.
- Session extraction keeps only top-level turns. A `user.message` is human
  only when it carries neither `parentAgentTaskId` nor a `source` field;
  `assistant.message` requires neither `parentToolCallId` nor
  `parentAgentTaskId`. Measured across a real 115-session corpus, 611 of 729
  user events were subagent task prompts and 94 were generated context,
  leaving 24 genuine human turns — filtering only on a `skill-` prefix would
  keep 657 and misattribute authorship roughly 27-fold. `reasoningText`,
  `reasoningOpaque`, and `transformedContent` are never extracted.
- Mining scans for credential shapes and blocks the write on a finding;
  `--redact` masks the spans and records a count. Repository, branch, and HEAD
  anchors are required and never invented, and candidates are project-isolated
  and write-once.
- Add a first-party `rag` memory provider backed by the bundled `local-rag`
  plugin, so **offline semantic recall no longer requires an external tool**.
  MemPalace becomes genuinely optional rather than the only route to
  meaning-based recall.
- Declare a hard dependency on `local-rag` in `plugin.json` and `apm.yml`, so
  installing `memory` deploys the retrieval engine on every host.
- Generalize the provider layer behind a declarative `ProviderSpec`. The
  projection, staging, atomic swap, projection marker, receipt, and backup
  pruning path is now shared by every provider. MemPalace behavior is unchanged
  and its test suite is the regression guard.
- `search` under `rag` binds hits back to local records, returning review,
  freshness, `source`, and `source_hash` with each result, and reports hits it
  cannot bind in `unmatched_hits` instead of dropping them.
- `search` degrades explicitly: when a provider is unreachable it falls back to
  lexical local search annotated with `degraded_from`, `degraded_reason`, and
  `degraded_detail`. Reconciliation is checked first, so a stale index refuses
  rather than being masked by a quiet fallback.
- `wake` reports `not-applicable` under `rag` without invoking the provider.
- `doctor` verifies the local-rag runtime before probing the CLI and refuses
  with the exact bootstrap command when the venv is missing or stale, closing
  the gap on hosts that do not run Claude's `SessionStart` hook. `doctor
  --bootstrap` builds it in place. The check applies only when the bundled
  `bin/rag` launcher is in use; a user-supplied `CONTEXT_KIT_RAG_BIN` manages
  its own runtime and is not gated.
- Receipts now carry a provider-neutral `store_path`, and `provider` reflects
  the configured provider. MemPalace receipts keep the `palace_path` key for
  continuity. The `recovery_status` value `restored-to-live-palace` is now
  `restored-to-live-store`.
- `capture` and `archive-handoff` record provider receipts for any configured
  provider, not only MemPalace.

## 0.2.3 — 2026-08-04

- Shorten the `memory-workflows` skill trigger to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.2.2 — 2026-07-27

- Shorten the discovery description(s) to free aggregate budget for the new
  `corpus-review` components. Triggers and scope are unchanged; the catalog
  budget is fixed, so every addition competes for the same remainder.

## 0.2.1 — 2026-07-25

- Adopt the evidence forms `verify` now defines for the `## Evidence` section,
  so provenance stays citable across the `verify` → `context-handoff` → `memory`
  chain. A bare command name is no longer an accepted source pointer; an
  observed result needs its observation source — `command-id=<allowlist key>` or
  `tool=<approved tool>@<target>` — plus an artifact pointer.

## 0.2.0 — 2026-07-19

- Add append-only review and freshness events over immutable memory records,
  including sequenced replay, validated transitions, and stale-lock recovery.
- Restrict active recall and provider projections to effective
  `accepted/current` records while preserving inactive history for audit.
- Add immutable provider receipts and guarded `sync-provider` dry-run/apply
  reconciliation with staged project-isolated palaces, backups, and
  live-palace projection markers.
- Require explicit provider synchronization after eligible captures or state
  changes; capture, handoff archival, and lifecycle hooks never mutate the
  provider palace. Opt-in hooks queue payloads locally for explicit review.
- Harden MemPalace compatibility checks against the tested 3.6.x CLI surface
  and add an opt-in real-CLI smoke test.
- Document project-scoped, server-enforced read-only GitHub Copilot MCP setup,
  provider qualification criteria, and the design-only status of Memora.

## 0.1.0 — 2026-07-19

- Add the provider-neutral `context-kit/memory-v1` record contract.
- Add capture, recall, review, and explicit handoff archival workflows.
- Add a tested Python 3 standard-library adapter for a separately installed
  MemPalace CLI with project-isolated storage and exact-argv execution.
- Derive collision-resistant project storage keys and publish write-once records
  atomically under concurrent capture.
- Enforce project provenance, complete record and handoff structure, empty
  allowlist boundaries, and local-only recall without MemPalace.
- Add opt-in Claude Stop, PreCompact, and detached SessionEnd capture hooks.
- Adopt Memora-inspired primary memories, cue anchors, freshness states,
  supersession history, rank-fusion guidance, and propose-only consolidation.
