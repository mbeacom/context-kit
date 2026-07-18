# Changelog

## 0.2.5 — 2026-07-18

- Lead host guidance with GitHub Copilot, then APM, then Claude Code in the
  `code-search` and `data-and-docs-search` skill portability notes.

## 0.2.4 — 2026-07-18

- Rebrand: the marketplace was renamed `productivity-skills` → `context-kit`.
  Updated the `homepage`/`repository` URLs and install commands
  (`… install code-search@context-kit`). GitHub redirects the old repository path,
  so existing marketplace registrations keep resolving.

## 0.2.3 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install code-search@context-kit`) alongside
  the Claude Code and GitHub Copilot flows. It declares the `retrieval-core`
  dependency (APM does not read the plugin.json `dependencies` field), so an APM
  install also deploys the retrieval spine.

## 0.2.2 — 2026-07-13

- Update GitHub Copilot guidance: Copilot CLI installs the plugin directly
  (`copilot plugin install`), replacing the manual `.github/skills` copy steps.

## 0.2.1 — 2026-05-29

- Document GitHub Copilot Agent Skills compatibility for `code-search` and
    `data-and-docs-search`, including copying `references/` with each skill.

## 0.2.0 — 2026-05-28

- Recommend `rtk` (rtk-ai/rtk) for the tools it wraps (`rg`/`grep`, `git`,
  `find`, `diff`) when installed; new `references/rtk.md`, pipe-safety guidance,
  scoped `Bash(rtk …)` permissions, and an optional `rtk` row in `check-tools.sh`.

## 0.1.0 — 2026-05-24

- Initial release: `code-search` and `data-and-docs-search` skills, `check-tools.sh`.
