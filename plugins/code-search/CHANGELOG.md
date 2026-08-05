# Changelog

## 0.3.4 — 2026-08-04

- Restore the `size/complexity metrics` cue to the `code-search` discovery
  description and shorten `data-and-docs-search` to pay for it. The 0.3.3 trim
  dropped the only mention of a modality this skill still owns, and no fixture
  covered it; a metrics positive example now guards the cue.

## 0.3.3 — 2026-08-04

- Shorten the `code-search` skill trigger to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.3.2 — 2026-08-03

- Shorten the discovery description(s) to free aggregate budget for the new
  `deep-review` components. Triggers and scope are unchanged; the catalog
  budget stays at 4096 characters rather than being raised.

## 0.3.1 — 2026-07-27

- Shorten the discovery description(s) to free aggregate budget for the new
  `corpus-review` components. Triggers and scope are unchanged; the catalog
  budget is fixed, so every addition competes for the same remainder.

## 0.3.0 — 2026-07-18

- Add a **code-intelligence** modality: symbol definitions, references, and call
  hierarchy via host LSP tools, GNU Global (`global`), or universal-ctags, with a
  `references/code-intelligence.md` guide and a decision-table row — filling the
  gap between lexical (`rg`) and structural (`sg`) search. `check-tools.sh` now
  reports `ctags` and `global`.

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
