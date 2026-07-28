# Changelog

## 0.2.3 — 2026-07-27

- Fix `/write-handoff` and `/resume-handoff` failing to load. Their
  `argument-hint: [artifact-path]` frontmatter was unquoted, so YAML resolved it
  to a flow sequence rather than a string and the host rejected both commands
  with `argument-hint must be a string`.

## 0.2.2 — 2026-07-25

- Record the `evidence (none)` case for an observation attempt that retained
  nothing citable, matching `verify` 0.3.1. The handoff contract previously
  implied every attempted collection could cite an observation source, leaving
  a no-artifact attempt with no valid form.

## 0.2.1 — 2026-07-25

- Align the verified-fact evidence slot with the forms `verify` now defines,
  instead of independently widening it to `path:line or command`. The
  observation form requires an observation source — `command-id=<allowlist key>`
  or `tool=<approved tool>@<target>` — plus its artifact pointer, and is
  reserved for a result that was actually observed; a bare command name is no
  longer accepted in the skill, the contract, or the artifact template.
- Require a runtime claim to be recorded as `unable-to-check` with the
  observation that would settle it, or cited from a real `runtime-evidence`
  collection.

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
