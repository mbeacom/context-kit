# Changelog

## 0.2.0 — 2026-07-19

- Keep handoffs out of automatic RAG and durable-memory ingestion.
- Define the separate, explicitly requested `/archive-handoff` path supplied by
  the memory plugin after structure and freshness validation.
- Clarify that archived handoffs are historical evidence, never authoritative
  current task state.

## 0.1.0 — 2026-07-18

- Add the portable `context-kit/handoff-v1` task-state artifact contract.
- Add authoritative manual `/write-handoff` and `/resume-handoff` commands.
- Add the read-only `handoff-compiler` subagent, composed with `verify`.
- Add deterministic structure and freshness validation with focused tests.
- Deliberately omit lifecycle hooks and automatic long-term RAG ingestion.
