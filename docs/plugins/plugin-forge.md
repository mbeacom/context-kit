# plugin-forge

!!! abstract "Author portable plugins"
    The house authoring toolkit: conventions, `/scaffold-plugin`,
    manifest/frontmatter validators, and deterministic catalog-quality and
    release-readiness gates. It's the same toolkit used to build this marketplace.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install plugin-forge@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install plugin-forge@context-kit
    ```

=== "Claude Code"

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
| **`scripts/check-skills.sh`** | Checks skill/agent discovery frontmatter, names, trigger phrasing, and per-description limits. |
| **`scripts/check-catalog-quality.sh`** | Enforces the 4096-character aggregate discovery budget, description-overlap policy, centralized fixture coverage, retrieval route/composition contracts, and agent output contracts. |
| **`scripts/test-catalog-quality.sh`** | Runs stdlib regression tests and a mocked, no-network plan-execute workflow smoke test. |
| **`scripts/test-release-readiness.sh`** | Runs hermetic release-readiness regression tests. |
| **`quality/retrieval-scenarios.json`** | Schema-v1 contract corpus for documented retrieval modalities, non-retrieval routes, composition steps, plugin/tool references, and near misses. |

## Use it in this repo

Scaffold a new plugin skeleton:

```text
/scaffold-plugin <new-plugin-name> "short description"
```

The command intentionally does **not** add the new plugin to
`.claude-plugin/marketplace.json` — add the hand-authored catalog entry only after
the plugin is complete and ready to ship.

Run the deterministic checks from the repository root before opening a PR:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/check-skills.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
```

!!! tip "Why the mirrored manifests"
    Each plugin ships both a `plugin.json` (read by Claude Code and Copilot) and a
    sibling `apm.yml` (read by APM). Their `name` and `version` must stay in
    lockstep; `description` is intentionally a more concise variant in `apm.yml`.
    The validator fails on `name`/`version` drift so the two never diverge.

The catalog gate treats discovery metadata as shared always-on context. It checks
all skill/agent descriptions against a 4096-character aggregate budget, flags
near-duplicate descriptions unless an exact pair is justified in policy, requires
central positive/negative fixtures for every component, and preserves explicit
agent output contracts.

The release-readiness gate stays separate from `check-manifests.sh`: the existing
check owns `name`/`version` mirroring, while release readiness resolves every
shipped source and dependency path, checks required metadata and assets, requires
the manifest version to be the latest changelog release, and compares both direct
and transitive dependency graphs.

The retrieval corpus is a separate contract from component discovery fixtures.
Each stable scenario declares a query and corpus cues, its expected primary
route, participating plugins and tools, exact named composition steps when
needed, a rationale, and at least one realistic near miss. The gate requires
coverage of all 14 routes (11 modalities plus handoff, verification, and
runtime-evidence escalation) and all nine named compositions.

!!! warning "Static fixtures are not routing proof"
    Discovery fixture and retrieval contract validation proves coverage,
    reference integrity, and basic hygiene, not that a model will route a prompt
    correctly. The workflow smoke test injects mocked agents and blocks network
    access; it checks orchestration shape, not live-model behavior.

To add a retrieval scenario, choose the route or composition boundary, add a
unique kebab-case ID with concrete corpus cues, copy a declared composition step
variant exactly when applicable, list only participating plugins and declared
tools, and add a near miss that crosses the boundary. Run the two catalog-quality
commands above.

Future scheduled live-model evaluation can consume the stable IDs, queries,
cues, expected selections, and near misses while recording provider/model
observations separately. Keep that probabilistic job credentialed, rate-limited,
and non-blocking; deterministic contracts remain the pull-request gate.

## At a glance

| | |
| --- | --- |
| **Category** | authoring |
| **Provides** | skill, command, manifest/frontmatter/catalog/release validators, regression and smoke tests |
| **Dependencies** | none |
| **License** | MIT |
