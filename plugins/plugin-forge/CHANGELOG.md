# Changelog

## 0.6.0 — 2026-07-25

- Add a pull-request version-bump gate (`scripts/version_bump.py`, run by
  `scripts/check-version-bump.sh`). It compares each plugin's changed files
  across `merge-base..HEAD` and fails when shipped content moved without a
  strictly-greater `plugin.json` version — the bump Claude Code needs to deliver
  the change at all. Path classification is fail-closed, with `README.md`,
  `LICENSE`, `CHANGELOG.md`, `tests/`, `docs/`, and `scripts/test-*.sh` exempt.
  A deliberate exemption uses a `Skip-Version-Bump: <plugin> - <reason>` commit
  trailer, read from the commit's real trailer block so a quoted example cannot
  suppress a bump, and echoed into the gate's output so the skip stays
  reviewable. Changed paths are read NUL-delimited so a non-ASCII filename
  cannot slip past the `plugins/` prefix check.
  Ships hermetic regression tests in `scripts/test-version-bump.sh`.
- Add a warning band and a per-component ceiling to the discovery budget.
  `aggregate_description_warn_ratio` (0.95) reports remaining headroom without
  failing, so near-capacity surfaces while there is still room to act;
  `component_description_max_chars` (384) stops one verbose description from
  consuming another component's headroom. The validator now reports remaining
  characters and the largest component description, and rejects a policy whose
  per-component ceiling exceeds the aggregate budget.
- Name the prefix-sharing near-matches when a discovery fixture no longer shares
  a content term with its description. Fixture matching is exact-token with no
  stemming, so a `code` → `codebase` edit silently unanchors a fixture; the
  message now points at the description token that changed rather than only at
  the fixture that noticed.

## 0.5.1 — 2026-07-25

- Extend the shipped quality corpus for `runtime-evidence`'s second collection
  path. The `runtime-evidence` route now declares both tools, a new
  `runtime-evidence-approved-optional-tool` scenario covers the case where no
  reviewed command can represent the claim (with a static near miss), a
  `verify-then-observe-optional-tool` scenario covers the same composition
  reached through that path, and the skill gains a positive discovery fixture
  for an approved browser observation.

## 0.5.0 — 2026-07-19

- Add a schema-v1 retrieval contract corpus covering all documented modalities,
  non-retrieval routes, named compositions, cross-plugin/tool references, and
  realistic near misses.
- Extend the existing deterministic catalog-quality validator and regression
  suite with route/composition coverage, referential integrity, exact step
  contract and per-variant coverage, and scenario-hygiene checks.
- Document contributor workflow and the boundary between blocking static
  contracts and future scheduled, non-blocking live-model routing evaluation.

## 0.4.0 — 2026-07-19

- Add a deterministic release-readiness gate with hermetic regression tests. It
  validates shipped catalog sources and release assets, manifest metadata,
  manifest-to-changelog version alignment, and matching direct/transitive
  dependency graphs across `plugin.json` and `apm.yml`.
- Wire the gate and tests through pre-commit/CI, and document the forward-only
  per-plugin tag and GitHub release process with fix-forward recovery guidance.

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
