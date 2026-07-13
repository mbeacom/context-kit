# Changelog

## 0.1.3 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install obsidian@productivity-skills`) alongside the
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
