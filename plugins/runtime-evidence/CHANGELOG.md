# Changelog

## 0.1.1 - 2026-07-25

- Specify the return leg of the handoff. `references/evidence-report.md` now
  names the observation evidence form defined by `verify` — an observation
  source plus an artifact pointer — requires reusing the original claim wording
  so the reassessed verdict replaces the earlier `unable-to-check`, and forbids
  restating an observation as a repository `path:line`.
- Make the approved optional-tool path reachable. The skill flow, the
  `runtime-investigator` method, and `/collect-runtime-evidence` previously
  stopped at "no reviewed command ID" before the optional-tool branch could run,
  so the browser/debugger/container observations that `optional-tools.md`
  allows precisely for claims no reviewed command can represent could never be
  produced. Each entry point now branches explicitly, gated on every
  `optional-tools.md` condition, and reports
  `Observation source: tool=<approved tool>@<target>` in place of the command
  ID. Allowlist selection on the runner path is unchanged.

## 0.1.0 - 2026-07-18

- Add the `runtime-evidence` skill and progressive-disclosure references.
- Add the `runtime-investigator` agent and `/collect-runtime-evidence` command.
- Add a strict user-owned allowlist runner with explicit cwd, timeout, output
  limits, structured artifacts, and focused tests.
- Refuse unsupported Windows execution before reading config or spawning a
  command; bounded pipe capture requires POSIX.
- Declare composition with `verify`, which already supplies `retrieval-core`.
