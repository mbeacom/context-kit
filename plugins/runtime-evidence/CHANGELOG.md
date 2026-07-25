# Changelog

## 0.1.1 - 2026-07-25

- Specify the return leg of the handoff. `references/evidence-report.md` now
  names the observation evidence form defined by `verify`
  (`evidence (command-id=<id>; report=<path>)`), requires reusing the original
  claim wording so the reassessed verdict replaces the earlier
  `unable-to-check`, and forbids restating an observation as a repository
  `path:line`.

## 0.1.0 - 2026-07-18

- Add the `runtime-evidence` skill and progressive-disclosure references.
- Add the `runtime-investigator` agent and `/collect-runtime-evidence` command.
- Add a strict user-owned allowlist runner with explicit cwd, timeout, output
  limits, structured artifacts, and focused tests.
- Refuse unsupported Windows execution before reading config or spawning a
  command; bounded pipe capture requires POSIX.
- Declare composition with `verify`, which already supplies `retrieval-core`.
