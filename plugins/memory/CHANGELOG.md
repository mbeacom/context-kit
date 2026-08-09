# Changelog

## 0.5.4 — 2026-08-08

- Assess criteria 2 and 5 explicitly for adrkit. The table claimed criteria
  "1, 3, 6–12" (nine) while the conclusion said 11 of 12, leaving 2 and 5
  silently unclassified. Both pass; the qualification is now internally complete.

## 0.5.3 — 2026-08-08

- Record adrkit in the provider decision table as a peer corpus rather than a
  provider, with the trust-model reason it cannot be one and the promotion path
  from a `type: decision` record to a ratified ADR (ADR-0003).

## 0.5.2 — 2026-08-08

- Fix a real failure in the pre-rename compatibility path. `store_env` and the
  runtime probe set only `CONTEXT_KIT_INDEXKIT_HOME`, but a legacy `bin/rag`
  launcher — which `_bundled_executable` can legitimately resolve — reads only
  `CONTEXT_KIT_LOCAL_RAG_HOME`. With `CONTEXT_KIT_DATA` redirected to the
  isolated provider store, that launcher looked for its venv inside the store
  and failed. Both names are now exported to the same resolved path.
- Restore pre-rename CHANGELOG entries to their original wording, so an old
  release's notes remain usable for diagnosing that version.

## 0.5.1 — 2026-08-08

- Move the `rag` provider's tested-version pin to indexkit 0.6.x, the release
  this adapter is exercised against.

## 0.5.0 — 2026-08-08

- Track the `local-rag` → `indexkit` rename (ADR-0007) without breaking existing
  installs. Provider resolution now accepts both names: `CONTEXT_KIT_INDEXKIT_BIN`
  with `CONTEXT_KIT_RAG_BIN` as fallback, both `indexkit` and `rag` on PATH, and
  either sibling plugin directory.
- Add declarative `legacy_bin_env` / `legacy_executables` to `ProviderSpec`, so the
  migration is provider data rather than branching in the resolver.
- The `rag` provider identifier is unchanged; existing configuration keeps working.

## 0.4.0 — 2026-08-05

- **Correct a documented falsehood.** Several docs claimed GitHub Copilot does
  not run Claude hooks. Verified false against a live Copilot CLI install
  (1.0.79): Copilot loads a plugin's `hooks/hooks.json` using the same
  PascalCase event names, honors an `additionalContext` string on stdout, and
  bootstraps plugin data at `~/.copilot/plugin-data/<marketplace>/<plugin>/`.
  APM still does not deploy hooks. Docs now state the real host matrix.
- `wake` is now a provider-neutral session digest built from local records
  rather than a MemPalace passthrough. Records are the system of record and a
  provider store is a projection of them, so the digest is identical under
  `none`, `rag`, and `mempalace`. It is bounded by record count and character
  budget, ordered by recency, flags drifted or missing sources, and offers
  `--format text` for injection.
- Add a `SessionStart` hook that emits that digest as `additionalContext`, so
  reviewed memory primes a session on both hosts that load hooks. Gated on its
  own `CONTEXT_KIT_MEMORY_RECALL_ON_START` switch rather than on
  `AUTO_CAPTURE`, because reading is not writing, and it degrades to `{}`
  rather than ever failing a session start.
- Add `audit`, a store-wide sweep for records whose cited source drifted or
  vanished. It reports and proposes an exact `record-state` command; unlike
  MemPalace's `sync` it never prunes, because evidence is the reason a memory
  can be trusted later and a moved file is not proof a decision was wrong.
- Tool-level hooks are deliberately **not** used. Measured on a real Copilot
  corpus, `preToolUse` and `postToolUse` fire 23,683 and 35,083 times against
  ~1,800 for the session boundaries, so hooking them would spawn a process per
  tool call to capture noise, and would amount to the continuous transcript
  harvesting the memory contract forbids.
- Drop the obsolete `wake-up` capability probe. `wake` is now built from local
  records for every provider, so requiring `wake-up` would refuse a MemPalace
  install over a command the adapter never calls. Delegation is not restored:
  MemPalace's `wake-up` returns its own mined L0/L1 context, which is
  unreviewed, and returning it would violate the active-only, reviewed-only
  recall contract.
- Fix venv resolution for the `rag` provider on Copilot. 0.3.0 dropped
  `CLAUDE_PLUGIN_DATA` because it is plugin-scoped, but that also lost the
  ability to locate the dependency. Both hosts lay plugin data out as
  `<root>/<plugin>`, so local-rag's home is resolved as a **sibling** of
  memory's, and only when it exists.

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
  plugin, so **offline semantic recall no longer requires an external memory
  provider**. MemPalace becomes genuinely optional rather than the only route
  to meaning-based recall. Ollama remains a required local runtime for
  embeddings, and `uv` is needed once to bootstrap the venv.
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
