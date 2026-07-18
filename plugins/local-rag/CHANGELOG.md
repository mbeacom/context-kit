# Changelog

## 0.1.4 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install local-rag@productivity-skills`) alongside the
  Claude Code and GitHub Copilot flows. As with Copilot, APM does not run the
  Claude `SessionStart` bootstrap hook — bootstrap `bin/rag` manually and use the
  `PRODUCTIVITY_SKILLS_*` env vars (see docs/APM.md).

## 0.1.3 — 2026-05-29

- Add GitHub Copilot/manual setup docs and portable `PRODUCTIVITY_SKILLS_*`
  environment variables while preserving `CLAUDE_PLUGIN_*` fallbacks.

## 0.1.2 — 2026-05-28

- Docs: clarify that `rag` is not rtk-wrapped (prefixing is a no-op); prefer
  `rtk` on the surrounding `rg` step, where `rtk rg -l` keeps paths raw. Permit
  `Bash(rg:*)`/`Bash(rtk rg:*)` so the hybrid `rg -l | rag query` example runs.

## 0.1.1 — 2026-05-24

Docs: correct the `rag status` skill example (reports counts/model/dim, not staleness).

## 0.1.0 — 2026-05-24

Initial engine: bin/rag CLI, uv venv bootstrap, plugin manifest (loader/store/embed/index/engine/cli land in subsequent commits).
