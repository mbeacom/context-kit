# Changelog

## 0.1.2 — 2026-07-18

- Update the `plan-execute-strategy` skill's advisor section to match the current
  Claude Code advisor doc (v2.1.210+): Fable 5 as the advisor is deliberately
  disabled by a remote rollout flag (dimmed `Fable 5 (temporarily unavailable)` row;
  `/advisor fable` and `--advisor fable` rejected), not merely a bug. Re-point the
  root-cause reference from #73019 to
  [#76199](https://github.com/anthropics/claude-code/issues/76199) (`advisorModel:
  fable` + any prior `tool_use` → deterministic `unavailable`; executor-irrelevant;
  Opus advisor immune; not context-size), and drop the imprecise "macOS and Windows /
  every main model" framing.
- Correct the "Fable main + Fable advisor is a no-op self-consult" claim: an
  equal-tier advisor is a legitimate independent second read, not a no-op.
- Note that a **Fable 5 main session currently runs with no advisor at all**, so
  delegation is the substitute for frontier-quality planning in a Fable session.
- Add verified hardening notes: the advisor is Anthropic-API-only (not Bedrock /
  Claude Platform on AWS / Google Cloud / Microsoft Foundry; via a gateway only if
  forwarded intact), `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` is a deterministic
  off-switch, and subagents inherit the advisor and re-check the pairing against
  their own model.

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
