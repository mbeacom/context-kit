# Changelog

## 0.4.0 — 2026-07-19

- Add durable memory as a distinct modality for prior decisions, constraints,
  procedures, preferences, and bounded episodes.
- Distinguish current task handoffs from long-term recall.
- Add recall-then-pin, recall-then-verify, and retrieve-then-expand compositions.
- Require source/freshness labels and current evidence when memory conflicts.

## 0.3.0 — 2026-07-18

- Route the new **code-intelligence** modality (symbol definitions, references,
  and call hierarchy) in the `retrieval-strategy` skill and `retrieval-strategist`
  agent, and add a "resolve then pin" composition (code-intelligence → `rg`).

## 0.2.6 — 2026-07-18

- Lead host guidance with GitHub Copilot, then APM, then Claude Code in the
  `retrieval-strategy` skill's portability note, and clarify that every host
  registers the marketplace before installing. Claude Code stays fully
  supported.

## 0.2.5 — 2026-07-18

- Rebrand: the marketplace was renamed `productivity-skills` → `context-kit`.
  Updated the `homepage`/`repository` URLs and install commands
  (`… install retrieval-core@context-kit`). GitHub redirects the old repository
  path, so existing marketplace registrations keep resolving.

## 0.2.4 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install retrieval-core@context-kit`)
  alongside the Claude Code and GitHub Copilot flows. No `.apm/` directory, so
  the plugin-native layout stays authoritative.

## 0.2.3 — 2026-07-13

- Update GitHub Copilot guidance: Copilot CLI installs the plugin directly
  (`copilot plugin install`), replacing the manual `.github/skills` copy steps.

## 0.2.2 — 2026-05-29

- Document GitHub Copilot Agent Skills compatibility and how to adapt the
  `retrieval-strategist` agent to Copilot custom-agent frontmatter.

## 0.2.1 — 2026-05-28

- Note rtk in the strategy defaults and the strategist agent: prefer
  `rtk`-prefixed forms of wrapped commands (`rg`/`git`/`find`/`diff`) when installed.

## 0.2.0 — 2026-05-24

- Route into the semantic (local-rag) and graph (obsidian) modalities now that
  they ship; document hybrid rerank via `rag query --allowlist`.

## 0.1.0 — 2026-05-24

- Initial release: `retrieval-strategist` agent and `retrieval-strategy` skill.
