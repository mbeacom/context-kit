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
| **`scripts/check-version-bump.sh`** | CI-only. Fails when a plugin's shipped content changed across `merge-base..HEAD` without a strictly-greater `plugin.json` version. |
| **`scripts/check-skills.sh`** | Checks skill/agent discovery frontmatter, names, trigger phrasing, and per-description limits. |
| **`scripts/check-catalog-quality.sh`** | Enforces the 4096-character aggregate discovery budget with a 95% warning band and a 384-character per-component ceiling, description-overlap policy, centralized fixture coverage, retrieval route/composition contracts, and agent output contracts. |
| **`scripts/test-catalog-quality.sh`** | Runs stdlib regression tests and a mocked, no-network plan-execute workflow smoke test. |
| **`scripts/test-release-readiness.sh`** | Runs hermetic release-readiness regression tests. |
| **`scripts/test-version-bump.sh`** | Runs hermetic version-bump gate regression tests. |
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
bash plugins/plugin-forge/scripts/test-version-bump.sh

# CI-only gate; run it locally against your PR base to preview the result
bash plugins/plugin-forge/scripts/check-version-bump.sh --base main
```

!!! tip "Why the mirrored manifests"
    Each plugin ships both a `plugin.json` (read by Claude Code and Copilot) and a
    sibling `apm.yml` (read by APM). Their `name` and `version` must stay in
    lockstep; `description` is intentionally a more concise variant in `apm.yml`.
    The validator fails on `name`/`version` drift so the two never diverge.

The catalog gate treats discovery metadata as shared always-on context. It checks
all skill/agent descriptions against a 4096-character aggregate budget and a
384-character per-component ceiling, warns (without failing) once the aggregate
reaches 95% of the budget so near-capacity surfaces before the next author hits
it, flags near-duplicate descriptions unless an exact pair is justified in
policy, requires central positive/negative fixtures for every component, and
preserves explicit agent output contracts. The budget is a self-imposed
catalog-wide discipline rather than a host limit: it is fixed rather than scaled
by component count, so the marketplace has a maximum viable always-on surface.

The release-readiness gate stays separate from `check-manifests.sh`: the existing
check owns `name`/`version` mirroring, while release readiness resolves every
shipped source and dependency path, checks required metadata and assets, requires
the manifest version to be the latest changelog release, and compares both direct
and transitive dependency graphs.

The version-bump gate closes the remaining hole in that trio: every other check
is diff-free, so none of them notices shipped content changing while the version
stands still — a green build that ships nothing. `check-version-bump.sh` compares
each plugin's changed files across `merge-base..HEAD` and fails when shipped
content moved without a strictly-greater `plugin.json` version. It is the only
CI-only gate here, because it is the only one that needs a merge base; run it
locally with `--base main`. Documentation-only (`README.md`, `docs/`, `LICENSE`),
test-only (`tests/`, `scripts/test-*.sh`), and `CHANGELOG.md` edits are exempt,
and classification is fail-closed: an unrecognized path counts as shipped. A
deliberate exemption goes in a commit trailer,
`Skip-Version-Bump: <plugin> - <reason>`, which the gate echoes into the CI log
so the skip is reviewable instead of silent.

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
