# plugin-forge

Plugin Forge helps authors create portable GitHub Copilot, APM, and Claude Code
plugins for the `context-kit` marketplace. It packages the house authoring
conventions, a scaffold command, and deterministic validators so new plugins
start with the right layout, keep `plugin.json` and `apm.yml` aligned, preserve
clear discovery metadata, and remain release-ready as the catalog grows.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install plugin-forge@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install plugin-forge@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install plugin-forge@context-kit
```

## Components

| Component | What it is |
| --- | --- |
| **`authoring-portable-plugins`** skill | The context-kit rulebook for plugin layout, manifest mirroring, portable install/env-var conventions, catalog entries, and release versioning. |
| **`/scaffold-plugin`** command | Creates a standard plugin skeleton under `plugins/<name>/` with `plugin.json`, `apm.yml`, README, CHANGELOG, LICENSE, and a starter skill. |
| **`scripts/check-manifests.sh`** | Validates every shipped plugin's `plugin.json` and sibling `apm.yml` have matching `name` and `version` fields. |
| **`scripts/check-release-readiness.sh`** | Validates shipped catalog sources, release metadata/assets, latest changelog versions, and direct/transitive dependency graph parity. |
| **`scripts/check-skills.sh`** | Validates each skill/agent's discovery frontmatter, name, trigger phrasing, and per-description length. |
| **`scripts/check-catalog-quality.sh`** | Enforces the aggregate discovery budget, description distinctness, centralized fixture coverage, retrieval route/composition contracts, and explicit agent output contracts. |
| **`scripts/test-catalog-quality.sh`** | Runs stdlib validator tests plus a mocked, no-network smoke test for the plan-big/execute-small workflow. |
| **`scripts/test-release-readiness.sh`** | Runs hermetic release-readiness regression tests. |

## Use it in this repo

Use `/scaffold-plugin <new-plugin-name> "short description"` to add a plugin
skeleton to this marketplace. The command intentionally does **not** add the new
plugin to `.claude-plugin/marketplace.json`; add the hand-authored catalog entry
only after the plugin is complete and ready to ship.

Run the deterministic checks from the repository root before opening a PR:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/check-skills.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
```

The policy, centralized positive/negative discovery fixtures, and structured
retrieval contract corpus live under `quality/`.
`quality/retrieval-scenarios.json` covers every documented retrieval modality,
non-retrieval route, and named composition with explicit corpus cues, expected
plugins/tools/steps, and near misses. Read
[`skills/authoring-portable-plugins/references/catalog-quality.md`](skills/authoring-portable-plugins/references/catalog-quality.md)
before adding or substantially changing a skill or agent description. These
static checks catch catalog and routing-contract regressions; they do not run or
score a model and do not claim live routing accuracy.
