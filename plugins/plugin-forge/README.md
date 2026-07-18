# plugin-forge

Plugin Forge helps authors create portable GitHub Copilot, APM, and Claude Code
plugins for the `context-kit` marketplace. It packages the house authoring
conventions, a scaffold command, and a manifest-drift validator so new plugins
start with the right layout and keep `plugin.json` and `apm.yml` aligned.

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

## Use it in this repo

Use `/scaffold-plugin <new-plugin-name> "short description"` to add a plugin
skeleton to this marketplace. The command intentionally does **not** add the new
plugin to `.claude-plugin/marketplace.json`; add the hand-authored catalog entry
only after the plugin is complete and ready to ship.

Run the drift check from the repository root before opening a PR:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
```
