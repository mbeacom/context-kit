# plugin-forge

!!! abstract "Author portable plugins"
    The house authoring toolkit: a conventions skill, a `/scaffold-plugin`
    command, and a manifest-drift validator that keeps `plugin.json` and `apm.yml`
    aligned. It's the same toolkit used to build this marketplace.

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

## Use it in this repo

Scaffold a new plugin skeleton:

```text
/scaffold-plugin <new-plugin-name> "short description"
```

The command intentionally does **not** add the new plugin to
`.claude-plugin/marketplace.json` — add the hand-authored catalog entry only after
the plugin is complete and ready to ship.

Run the drift check from the repository root before opening a PR:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
```

!!! tip "Why the mirrored manifests"
    Each plugin ships both a `plugin.json` (read by Claude Code and Copilot) and a
    sibling `apm.yml` (read by APM). Their `name` and `version` must stay in
    lockstep; `description` is intentionally a more concise variant in `apm.yml`.
    The validator fails on `name`/`version` drift so the two never diverge.

## At a glance

| | |
| --- | --- |
| **Category** | authoring |
| **Provides** | skill, `/scaffold-plugin` command, `check-manifests.sh` validator |
| **Dependencies** | none |
| **License** | MIT |
