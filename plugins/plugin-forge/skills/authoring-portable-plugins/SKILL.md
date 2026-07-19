---
name: authoring-portable-plugins
description: "Use when creating a new plugin (or editing one) for a multi-host GitHub Copilot / APM / Claude Code marketplace — the required manifest files, the plugin.json ⇆ apm.yml mirroring rule, portable env-var and install conventions, the component directory layout, and how to add it to the catalog."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Bash
---

# Authoring Portable Plugins

Use this skill as the house rulebook for `context-kit` plugins: a Claude Code
plugin marketplace that is also installable by GitHub Copilot CLI and APM. Keep
new plugin knowledge portable across those hosts, and keep host-specific wiring
isolated to manifests, install instructions, hooks, commands, or scripts.

## Required invariants

Create each plugin under `plugins/<name>/` and include these files before treating
it as shippable:

- `.claude-plugin/plugin.json` with `$schema`, `name`, `displayName`, `version`,
  `description`, `author`, `homepage`, `repository`, `license`, and `keywords`.
- A sibling `apm.yml` that mirrors the plugin metadata for Agent Package Manager.
- `README.md`, `CHANGELOG.md`, and `LICENSE` using MIT licensing for Mark Beacom.
- The component directories the plugin actually ships: `skills/`, `agents/`,
  `commands/`, `scripts/`, hooks, MCP config, or other support files as needed.

Keep `.claude-plugin/` reserved for `plugin.json`. Put every component directory
at the plugin root.

## Manifest mirroring rule

Keep `plugin.json` and `apm.yml` aligned every time a plugin ships:

- Keep `name` and `version` **strictly identical**. Claude Code uses `version` as
  the cache key, so bump `plugin.json` and `apm.yml` together to ship updates.
- Keep author, license, homepage, repository, and keywords aligned with the
  plugin manifest. Let `apm.yml` use a shorter `description` tuned for CLI
  listings while `plugin.json` can carry the fuller description.
- Do **not** add an `.apm/` directory. The plugin-native layout remains the
  authoritative source for GitHub Copilot, APM, and Claude Code.
- Put inter-plugin APM dependencies in `apm.yml` because APM does not read the
  Claude `plugin.json` `dependencies` field. Use `dependencies.apm` with sibling
  local paths such as `- path: ../retrieval-core`.
- Never run `apm pack` to regenerate `.claude-plugin/marketplace.json`. Generated
  output drops the per-plugin `category` field; the upstream fix
  `microsoft/apm#2189` is treated as unreleased for this repo.

Run `${CLAUDE_PLUGIN_ROOT}/scripts/check-manifests.sh` from any working directory
to catch `name` or `version` drift across all plugins, and
`${CLAUDE_PLUGIN_ROOT}/scripts/check-skills.sh` to catch skill/agent discovery
frontmatter problems (a missing/oversized `description`, or a `name` that does
not match its directory or file). Run
`${CLAUDE_PLUGIN_ROOT}/scripts/check-catalog-quality.sh` for cross-catalog checks:
the aggregate always-on description budget, dangerously similar trigger
descriptions, centralized positive/negative fixture coverage, and explicit agent
output-contract markers. All run in pre-commit and CI.

## Component layout

Place components at the plugin root:

- `skills/<skill-name>/SKILL.md`, with optional `references/` for progressive
  disclosure details.
- `agents/<agent-name>.md` for subagents.
- `commands/<command-name>.md` for slash commands.
- `scripts/` for deterministic helper scripts.
- `hooks/` or `.mcp.json` only when the plugin actually needs them.

Use kebab-case for plugin names, skill directories, command files, agent files,
and scripts. Prefer a few well-scoped skills with reference files over many tiny
skills; always-on skill metadata has a context cost.

Give every `SKILL.md` and `agents/*.md` a `name` that matches its directory or
file and a `description` that starts with a trigger ("Use when …", "Use to …").
GitHub Copilot and Claude Code both decide when to load a component from those
two fields, so `check-skills.sh` enforces them. Add positive and negative query
examples to `plugin-forge/quality/discovery-fixtures.json` at the same time; the
catalog gate requires exact coverage for every current skill and agent.

## Portability rules

Write reusable bodies for GitHub Copilot, APM, and Claude Code rather than for a
single host. Use these conventions:

- Prefer portable environment variables named `CONTEXT_KIT_*`; document
  `CLAUDE_PLUGIN_*` as the Claude fallback when needed. For example,
  `CONTEXT_KIT_DATA` can fall back to `CLAUDE_PLUGIN_DATA`.
- Put shared, host-neutral project memory in a root `AGENTS.md` — the cross-tool
  project-memory convention — and let `CLAUDE.md` and
  `.github/copilot-instructions.md` point to it and add only host-specific notes.
- Use `${CLAUDE_PLUGIN_ROOT}` for paths to scripts or bundled resources inside a
  plugin. Do not hardcode install locations or rely on the current working
  directory.
- Document all install flows:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install <plugin-name>@context-kit
apm marketplace add mbeacom/context-kit
apm install <plugin-name>@context-kit
/plugin marketplace add mbeacom/context-kit
/plugin install <plugin-name>@context-kit
```

Keep Claude-only features clearly labeled as Claude fallbacks or extensions, and
pair them with a host-neutral convention where one exists.

## Catalog and release step

Add `.claude-plugin/marketplace.json` entries only when a plugin is ready to ship.
The catalog is hand-authored and shared by GitHub Copilot, APM, and Claude Code; stubs
stay unlisted. A ready entry includes:

- `name`
- `source`
- `description`
- `category`
- `tags`

Bump both manifest versions for any shipped update before asking the parent repo
to wire the catalog entry.

## Resources and workflows

- Read `references/manifests.md` for side-by-side `plugin.json` and `apm.yml`
  examples, dependency syntax, versioning, and the `apm pack` warning.
- Read `references/layout.md` for the canonical tree, marketplace entry shape,
  and validation commands.
- Read `references/catalog-quality.md` for the deterministic description-budget,
  similarity, fixture, output-contract, and workflow-smoke-test policies.
- Use `/scaffold-plugin <new-plugin-name> "short description"` to create a
  standard starter under `plugins/<name>/` without adding it to the catalog.
- Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-manifests.sh` to validate manifest
  drift, and `bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-skills.sh` to validate
  skill/agent discovery frontmatter, across the repository. Run
  `bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-catalog-quality.sh` for aggregate
  discovery quality and `bash ${CLAUDE_PLUGIN_ROOT}/scripts/test-catalog-quality.sh`
  for the hermetic validator and workflow smoke tests.
