# Changelog

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
