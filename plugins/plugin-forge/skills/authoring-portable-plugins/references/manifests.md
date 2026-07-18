# Manifest reference

Every `context-kit` plugin has two manifests:

- `.claude-plugin/plugin.json` for Claude Code and GitHub Copilot compatible
  plugin metadata.
- `apm.yml` for Agent Package Manager metadata and APM-native dependencies.

Keep `name` and `version` strictly identical. Keep the remaining metadata aligned
unless the field has a host-specific reason to differ. The intended difference is
`description`: `plugin.json` may be fuller, while `apm.yml` should be concise for
CLI listings.

## Matched pair

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "example-plugin",
  "displayName": "Example Plugin",
  "version": "0.1.0",
  "description": "Author-ready description for Claude Code, GitHub Copilot, and marketplace readers. It can be one or two sentences.",
  "author": { "name": "Mark Beacom" },
  "homepage": "https://github.com/mbeacom/context-kit",
  "repository": "https://github.com/mbeacom/context-kit",
  "license": "MIT",
  "keywords": ["example", "plugin", "context-kit"]
}
```

```yaml
# Agent Package Manager (APM) manifest — https://github.com/microsoft/apm
# Lets APM users install this plugin alongside the Claude Code / GitHub Copilot
# flows: `apm install example-plugin@context-kit`. There is no `.apm/`
# directory, so the plugin-native layout (.claude-plugin/plugin.json + skills/)
# stays authoritative; APM consumes it as a plugin collection.
# Keep name/version in sync with .claude-plugin/plugin.json; keep description as
# the concise APM/CLI-listing variant of the plugin.json description.
name: example-plugin
version: 0.1.0
description: Concise CLI listing description for the same plugin.
author: Mark Beacom
license: MIT
homepage: https://github.com/mbeacom/context-kit
repository: https://github.com/mbeacom/context-kit
keywords: [example, plugin, context-kit]
```

## Field rules

| Field | `plugin.json` | `apm.yml` | Rule |
| --- | --- | --- | --- |
| `$schema` | Required schema URL | Not used | Keep only in `plugin.json`. |
| `name` | Kebab-case plugin id | Same value | Must be identical. |
| `displayName` | Human display name | Not used | Keep only in `plugin.json`. |
| `version` | Semver string | Same semver | Must be identical; bump both to ship. |
| `description` | Fuller marketplace description | Concise CLI description | Keep semantically aligned; wording may differ. |
| `author` | Object, `{ "name": "Mark Beacom" }` | String, `Mark Beacom` | Same author, host-specific shape. |
| `homepage` | Repo URL | Same URL | Keep aligned. |
| `repository` | Repo URL | Same URL | Keep aligned. |
| `license` | `MIT` | `MIT` | Keep aligned. |
| `keywords` | JSON array | YAML inline array | Keep aligned unless a host needs different discovery terms. |

## Dependencies

Claude Code and Copilot can read a `plugin.json` dependency list such as:

```json
{
  "dependencies": ["retrieval-core"]
}
```

APM does not read that field. Mirror inter-plugin dependencies in `apm.yml` with
sibling local paths:

```yaml
dependencies:
  apm:
    # APM resolves sibling plugin paths inside the same repository.
    - path: ../retrieval-core
```

Use local paths for plugins in this repo so forks and local installs keep working.
Do not replace them with hardcoded GitHub owner/repo references.

## Release and catalog warnings

Bump both manifest versions for every shipped change. Claude Code uses
`plugin.json` `version` as the cache key, so pushing commits without a version
bump may not deliver the update.

Keep `.claude-plugin/marketplace.json` hand-authored. Do **not** run `apm pack` to
regenerate it: generated output drops the per-plugin `category` field and rewrites
the shared catalog. The category fix in `microsoft/apm#2189` is merged but treated
as unreleased here; even after release, re-check generated output before changing
this rule.
