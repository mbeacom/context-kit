# Changelog

## 0.2.2 — 2026-08-03

- Shorten the discovery description(s) to free aggregate budget for the new
  `deep-review` components. Triggers and scope are unchanged; the catalog
  budget stays at 4096 characters rather than being raised.

## 0.2.1 — 2026-07-27

- Shorten the discovery description(s) to free aggregate budget for the new
  `corpus-review` components. Triggers and scope are unchanged; the catalog
  budget is fixed, so every addition competes for the same remainder.

## 0.2.0 — 2026-07-18

- Add **MCP servers** as a first-class layer in the `context-budget` decision
  matrix — when to reach for a live external system vs a skill, CLI, or subagent —
  with a `references/mcp-as-context.md` guide and the reminder that every connected
  server's tool schemas are an always-on context cost.

## 0.1.1 — 2026-07-18

- Lead host guidance with GitHub Copilot, then APM, then Claude Code in the
  `context-budget` skill's portability note and install snippet.

## 0.1.0 — 2026-07-18

- Initial release of the skill-only `context-steering` plugin.
- Add the `context-budget` decision skill for choosing the cheapest guidance layer that still fires when needed.
- Ship inert path-scoped rule and hook examples for copy-paste adaptation.
