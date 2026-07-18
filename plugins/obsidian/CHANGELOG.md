# Changelog

## 0.1.5 — 2026-07-18

- Lead the plugin README's host list with GitHub Copilot, APM, then Claude Code.

## 0.1.4 — 2026-07-18

- Rebrand: the marketplace was renamed `productivity-skills` → `context-kit`. The
  vault env var is now `CONTEXT_KIT_OBSIDIAN_VAULT`; the former
  `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` still resolves as a deprecated alias. Updated
  URLs and install commands (`… install obsidian@context-kit`).

## 0.1.3 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install obsidian@context-kit`) alongside the
  Claude Code and GitHub Copilot flows. Set the vault path via
  `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` (APM has no Claude userConfig).

## 0.1.2 — 2026-05-29

- Document GitHub Copilot compatibility and prefer
  `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` in portable examples, with the Claude
  vault option retained as a fallback.

## 0.1.1 — 2026-05-28

- Note that `rtk rg -l` compacts the `rg` fallback output while keeping `-l`
  raw so piped note paths survive; `fd`/`obsidian`/`rag` aren't rtk-wrapped and
  pass through unchanged.

## 0.1.0 — 2026-05-24

Replace placeholder stub with the skill-only Obsidian RAG bridge (graph/tags →
local-rag allowlist). Authoring/Bases/Canvas deferred to kepano/obsidian-skills.
