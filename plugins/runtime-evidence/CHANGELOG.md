# Changelog

## 0.1.1 - 2026-07-25

- Specify the return leg of the handoff. `references/evidence-report.md` now
  names the observation evidence form defined by `verify` — an observation
  source plus an artifact pointer — requires reusing the original claim wording
  so the reassessed verdict replaces the earlier `unable-to-check`, and forbids
  restating an observation as a repository `path:line`.
- Make the approved optional-tool path reachable, and honest about where it can
  run. The skill flow, the `runtime-investigator` method, and
  `/collect-runtime-evidence` previously stopped at "no reviewed command ID"
  before the optional-tool branch could run, so the browser/debugger/container
  observations that `optional-tools.md` allows precisely for claims no reviewed
  command can represent could never be produced. That path now runs in the main
  agent, not the subagent — a subagent's tool grant is fixed, so a host-exposed
  browser or debugger is not reachable inside it — and the skill documents both
  collection paths side by side. Allowlist selection on the runner path is
  unchanged.
- Give the optional-tool path its own field set instead of claiming it can
  "keep every other field". Process exit data, runner-report environment
  metadata, and the config digest do not exist for a browser or debugger
  observation; the contract now defines observed-state, artifact, and
  `not-applicable` handling per field.
- Update the skill, agent, and manifest descriptions so both paths are
  discoverable and the install metadata no longer says the plugin runs only
  pre-reviewed command IDs. Adds an optional-tool discovery fixture.

## 0.1.0 - 2026-07-18

- Add the `runtime-evidence` skill and progressive-disclosure references.
- Add the `runtime-investigator` agent and `/collect-runtime-evidence` command.
- Add a strict user-owned allowlist runner with explicit cwd, timeout, output
  limits, structured artifacts, and focused tests.
- Refuse unsupported Windows execution before reading config or spawning a
  command; bounded pipe capture requires POSIX.
- Declare composition with `verify`, which already supplies `retrieval-core`.
