# Changelog

## 0.1.1 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install plan-execute@productivity-skills`) alongside
  the Claude Code and GitHub Copilot flows.

## 0.1.0 — 2026-07-13

- Initial release: the `plan-execute-strategy` skill, the
  `/plan-big-execute-small` command, the bundled
  `plan-big-execute-small` Workflow script, and the `execution-worker`
  subagent. Promotes the former repo-root `workflows/` template into an
  installable plugin.
- The bundled workflow runs an independent read-only **verify** stage between
  Execute and Synthesize, so the synthesizer weighs re-checked findings instead of
  grading its own inputs.
- `execution-worker` hardened with contract discipline: tight scope, stop-and-report
  on a wrong spec, mandatory deviation disclosure, a shared-tree git-write ban, and a
  capped structured report.
- Deferred by design: a guaranteed read-only `investigation-worker` (Read/Grep/Glob
  only) is the sanctioned next agent if a workload needs one — one broad worker
  covers the current need.
