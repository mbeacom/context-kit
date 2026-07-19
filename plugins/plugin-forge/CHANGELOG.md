# Changelog

## 0.3.0 — 2026-07-18

- Add a deterministic, Python-stdlib catalog quality gate that enforces the
  aggregate always-on discovery-description budget, flags dangerously similar
  triggers with an explicit threshold/allowlist policy, requires centralized
  positive and negative discovery fixtures for every skill and agent, and
  validates configured agent output-contract markers.
- Add hermetic success and intentional-failure tests plus a no-network smoke test
  for the existing plan-big/execute-small workflow using mocked workflow agents.
  Wire both checks through pre-commit; keep live-model routing evaluation
  documented as future scheduled, non-blocking work.

## 0.2.0 — 2026-07-18

- Add `scripts/check-skills.sh`, a validator for skill/agent discovery frontmatter
  (`name` matches its directory/file; `description` present, trigger-phrased, and
  within length bounds). Document it in the `authoring-portable-plugins` skill and
  wire it, with `check-manifests.sh`, into pre-commit. Note the root `AGENTS.md`
  convention for portable, host-neutral project memory.

## 0.1.1 — 2026-07-18

- Lead the multi-host authoring guidance and install-flow example with GitHub
  Copilot, then APM, then Claude Code in the `authoring-portable-plugins` skill
  and the plugin description.

## 0.1.0 — 2026-07-18

- Initial release of the `plugin-forge` authoring plugin.
- Add the `authoring-portable-plugins` skill for context-kit plugin conventions.
- Add the `/scaffold-plugin` command for portable plugin skeletons.
- Add `scripts/check-manifests.sh` to detect plugin manifest drift.
