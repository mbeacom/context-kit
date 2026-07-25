# Changelog

## 0.1.2 - 2026-07-25

- Run the approved optional-tool path in the main agent instead of the
  `runtime-investigator` subagent. A subagent's tool grant is fixed, so a
  host-exposed browser, debugger, or container tool is not reachable inside it;
  routing the branch there made it no more executable than before. The subagent
  returns to command-only and says why when it reports `blocked`, and
  `/collect-runtime-evidence` delegates only the runner path.
- Give the optional-tool path its own field set instead of reusing the runner's.
  Process exit data, runner-report environment metadata, and the config digest
  do not exist for a browser observation, so the contract now defines
  observed-state and `not-applicable` handling per field — including
  `Reproduction command ID: not-applicable` on a `blocked` result, which by
  definition has no matching ID.
- Require at least one durable artifact on the optional-tool path. `verify`'s
  observation evidence form needs a pointer, so an observation nobody can
  inspect is not citable: it now stays `unable-to-check` naming what would need
  to be captured, rather than being recorded as weaker evidence.
- Scope "bounded" to the runner. The skill, agent, and manifest descriptions
  applied the runner's timeout and output caps to browser observations, which
  the plugin does not bound at all.
- Scope prerequisites to the path that has them. The skill `compatibility`
  field, the plugin README, and the docs stated Python 3, POSIX, and Windows
  refusal as unconditional, but those belong to the bundled runner. The
  optional-tool path ships no runner and needs only an approved, host-exposed
  tool, so it remains available where the wrapper is not — including on Windows.
- Stop requiring an allowlist config before the optional-tool branch is
  reachable. `/collect-runtime-evidence` demanded a config up front, so the
  branch for claims no reviewed command can represent was gated on the very
  thing it exists to work without.
- Document both collection paths side by side, and describe the optional-tool
  path as the weaker boundary wherever the catalog covers this plugin —
  including the security boundary map, where allowlist-only wording understated
  the surface.

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
- Document the optional-tool path as the weaker boundary wherever the catalog
  describes this plugin, including the security boundary map. It is bounded by
  the user's approval and the host, not by anything this plugin enforces.

## 0.1.0 - 2026-07-18

- Add the `runtime-evidence` skill and progressive-disclosure references.
- Add the `runtime-investigator` agent and `/collect-runtime-evidence` command.
- Add a strict user-owned allowlist runner with explicit cwd, timeout, output
  limits, structured artifacts, and focused tests.
- Refuse unsupported Windows execution before reading config or spawning a
  command; bounded pipe capture requires POSIX.
- Declare composition with `verify`, which already supplies `retrieval-core`.
