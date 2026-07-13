# Changelog

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
