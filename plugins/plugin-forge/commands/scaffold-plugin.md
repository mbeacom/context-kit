---
description: Scaffold a new portable plugin skeleton (plugin.json + apm.yml + README + CHANGELOG + LICENSE + a starter skill) under plugins/<name>/, following the context-kit conventions.
argument-hint: '<new-plugin-name> ["short description"]'
---

Scaffold a new portable `context-kit` plugin from `$ARGUMENTS`.

First read and apply the `authoring-portable-plugins` skill, including its
`references/manifests.md` and `references/layout.md` files.

If `$ARGUMENTS` is empty, ask for the plugin name and do not scaffold anything.

Validate the requested plugin name before writing files:

- Extract the first argument as `<new-plugin-name>` and treat the remaining text,
  if any, as the short description.
- Require kebab-case: lowercase letters, numbers, and single hyphens only.
- Reject leading hyphens, trailing hyphens, doubled hyphens, spaces, underscores,
  or uppercase letters.
- Refuse to overwrite an existing `plugins/<new-plugin-name>/` directory.

Create files only under `plugins/<new-plugin-name>/`:

```text
plugins/<new-plugin-name>/
├── .claude-plugin/plugin.json
├── apm.yml
├── README.md
├── CHANGELOG.md
├── LICENSE
└── skills/<new-plugin-name>/SKILL.md
```

Use these skeleton rules:

- Set both manifest versions to `0.1.0`.
- Use author `Mark Beacom`; in `plugin.json`, use `{ "name": "Mark Beacom" }`.
- Use license `MIT` and the standard copyright line
  `Copyright (c) 2026 Mark Beacom`.
- Use homepage and repository `https://github.com/mbeacom/context-kit`.
- Keep `plugin.json` and `apm.yml` `name` and `version` strictly identical.
- Write an `apm.yml` description as the concise CLI-listing variant of the
  `plugin.json` description.
- Leave a starter `skills/<new-plugin-name>/SKILL.md` with valid frontmatter:
  `name`, a specific `description`, `license: MIT`, `metadata.author`,
  `metadata.version: "0.1.0"`, and any needed `allowed-tools`.
- Keep all component directories at the plugin root, never under
  `.claude-plugin/`.

Do **not** add the plugin to `.claude-plugin/marketplace.json` yet. After
scaffolding, tell the user the exact catalog entry to add when the plugin is
ready, using this shape:

```json
{
  "name": "<new-plugin-name>",
  "source": "./plugins/<new-plugin-name>",
  "description": "<short description>",
  "category": "development",
  "tags": ["plugin"]
}
```

Validate the result before reporting completion:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-manifests.sh
claude plugin validate ./plugins/<new-plugin-name> --strict
```

If `claude` is not available on `PATH`, report that plugin validation was skipped
and still run the manifest check. Report created files, validation output, and the
catalog entry for the user to add when ready.
