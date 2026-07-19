# Layout reference

Use this tree as the canonical `context-kit` plugin layout. Create only the
component directories a plugin actually ships.

```text
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json          # Required Claude Code / Copilot manifest.
├── apm.yml                  # Required APM manifest; mirrors name/version.
├── README.md                # Install, components, and usage notes.
├── CHANGELOG.md             # Versioned release notes.
├── LICENSE                  # MIT license for Mark Beacom.
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md         # Required for each skill.
│       └── references/      # Optional progressive-disclosure detail.
├── agents/
│   └── <agent-name>.md      # Optional subagent definitions.
├── commands/
│   └── <command-name>.md    # Optional slash commands.
├── scripts/
│   └── <helper>.sh          # Optional deterministic helpers.
├── hooks/
│   └── hooks.json           # Optional Claude hook config.
└── .mcp.json                # Optional MCP server definitions.
```

Keep component directories at the plugin root. Never put `skills/`, `agents/`,
`commands/`, `scripts/`, `hooks/`, or `.mcp.json` inside `.claude-plugin/`; that
directory holds only `plugin.json`.

## Marketplace entry shape

Add a plugin to `.claude-plugin/marketplace.json` only when it is complete and
ready to ship. The catalog is hand-authored and shared by Claude Code, GitHub
Copilot, and APM.

```json
{
  "name": "example-plugin",
  "source": "./plugins/example-plugin",
  "description": "Short marketplace description of the shipped plugin.",
  "category": "development",
  "tags": ["authoring", "plugin", "context-kit"]
}
```

Use the category and tags that match the plugin's actual purpose. Do not list
half-built stubs.

## Validation commands

Run the smallest checks that cover the plugin being changed:

```bash
claude plugin validate ./plugins/<name> --strict
bash plugins/plugin-forge/scripts/check-manifests.sh
bash plugins/plugin-forge/scripts/check-skills.sh
pre-commit run --all-files
```

For a fast manifest-only check from any directory, pass the plugins directory or
let the script resolve it relative to the plugin installation:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
bash /path/to/plugin-forge/scripts/check-manifests.sh /path/to/context-kit/plugins
```

Use `pre-commit run --all-files` before a full PR because it covers markdownlint,
shellcheck, repo hygiene, and the manifest + skill-frontmatter checks.
