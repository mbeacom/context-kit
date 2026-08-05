# Changelog

## 0.1.8 — 2026-08-04

- Shorten the `plan-execute-strategy` skill and `execution-worker` agent triggers to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.1.7 — 2026-08-03

- Shorten the discovery description(s) to free aggregate budget for the new
  `deep-review` components. Triggers and scope are unchanged; the catalog
  budget stays at 4096 characters rather than being raised.

## 0.1.6 — 2026-07-27

- Shorten the discovery description(s) to free aggregate budget for the new
  `corpus-review` components. Triggers and scope are unchanged; the catalog
  budget is fixed, so every addition competes for the same remainder.

## 0.1.5 — 2026-07-25

- Target the current model generation in `plan-execute-strategy`: name **Opus 5**
  and **Sonnet 5** instead of 4.x examples wherever the skill specifies a model.
  The capability-pairing bullet now states that an Opus 5 main accepts Fable or any
  Opus 4.7-or-later advisor (Opus 5 included) and rejects Sonnet 5 / Opus 4.6, and
  adds the Sonnet 5 main row (accepts Fable, Opus, or Sonnet 5; rejects Sonnet 4.6).
  The advisor is Anthropic-API-only, so `/advisor opus` there resolves to Opus 5 —
  the documented workaround while Fable-as-advisor is rolled back.
- Add the provider-scoped alias caveat for **delegation**: `opus` / `sonnet` track
  the recommended version *for your provider*, not the newest model. On the
  Anthropic API they are Opus 5 / Sonnet 5, but `sonnet` is Sonnet 4.6 on Claude
  Platform on AWS and Sonnet 4.5 on Amazon Bedrock / Google Cloud, and Microsoft
  Foundry resolves `opus` to Opus 4.6 — precisely the runtimes where delegation is
  the only option, since the advisor can't reach them. Pin `claude-opus-5` /
  `claude-sonnet-5` or set `ANTHROPIC_DEFAULT_{OPUS,SONNET}_MODEL` to force the
  current generation, and note the client floors (Opus 5 needs v2.1.219+, Sonnet 5
  needs v2.1.197+).

## 0.1.4 — 2026-07-18

- Lead the install section with GitHub Copilot, then APM (new block), then
  Claude Code in the plugin README.

## 0.1.3 — 2026-07-18

- Rebrand: the marketplace was renamed `productivity-skills` → `context-kit`.
  Updated the `homepage`/`repository` URLs and install commands
  (`… install plan-execute@context-kit`). GitHub redirects the old repository path,
  so existing marketplace registrations keep resolving.

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
  install this plugin (`apm install plan-execute@context-kit`) alongside
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
