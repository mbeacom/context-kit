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
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/check-skills.sh
bash plugins/plugin-forge/scripts/check-commands.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
bash plugins/plugin-forge/scripts/test-commands.sh
pre-commit run --all-files
```

For a fast manifest-only check from any directory, pass the plugins directory or
let the script resolve it relative to the plugin installation:

```bash
bash plugins/plugin-forge/scripts/check-manifests.sh
bash /path/to/plugin-forge/scripts/check-manifests.sh /path/to/context-kit/plugins
```

Use `pre-commit run --all-files` before a full PR because it covers markdownlint,
shellcheck, repo hygiene, manifest + skill-frontmatter + command-frontmatter
checks, aggregate catalog quality, release readiness, regression tests, and the
hermetic workflow smoke test.

## Command frontmatter

A command whose frontmatter field resolves to the wrong YAML type does not
degrade — it fails to load. `check-commands.sh` enforces this contract for every
`plugins/*/commands/**/*.md`:

| Field | Type | Notes |
| --- | --- | --- |
| `description` | string | Required; shown in the command picker. |
| `argument-hint` | string | **Quote bracketed hints**: `"[artifact-path]"`. |
| `allowed-tools` | string | e.g. `Read, Grep, Bash(git:*)`. |
| `model` | string | Optional model override. |
| `disable-model-invocation` | boolean | Unquoted `true` / `false`. |

Any other top-level key is rejected, because a typo such as `argument_hint` is
silently ignored by the host — the same invisible-failure mode the gate exists
to prevent. Add a new key to `STRING_FIELDS` or `BOOL_FIELDS` in
`scripts/command_frontmatter.py` when a host genuinely adds one.

Quote a value that YAML would otherwise resolve to a non-string:

```yaml
# Wrong — a flow sequence, so the host reports `argument-hint must be a string`.
argument-hint: [artifact-path]

# Right.
argument-hint: "[artifact-path]"
```

The same trap applies to a value that reads as a bool (`yes`, `off`), a number
(`1.2`), a date (`2026-01-01`), or a mapping (`{a: b}`). Angle-bracket hints such
as `argument-hint: <runtime claim>` are already plain scalars and need no
quoting, but quoting them is still safe.

Three more shapes are rejected, because each one also stops the command loading:

```yaml
description: # TODO          # comment-only, so YAML resolves it to null
description: "unterminated   # a quoted scalar with no closing quote
description:                 # a nested mapping, not a string
  text: value
```

A plain scalar containing `": "` is a YAML parse error and is rejected too.

Type resolution ports PyYAML's implicit resolvers (YAML 1.1) verbatim, so the
gate never fails a value YAML would accept. That has deliberate consequences
worth knowing: `1e3` and `1.0e3` are strings because the exponent form needs an
explicit sign, `0o17` is a string because YAML 1.1 octal is `017`, and `y` / `n`
are strings because PyYAML omits the single-letter booleans.

## Agent frontmatter

`tools` and `skills` look interchangeable and are not. `tools` is a
comma-separated string; **`skills` is a YAML list**, and using the `tools` shape
for it is the single portability trap in an agent file:

```yaml
# Wrong — Copilot rejects the WHOLE frontmatter:
#   "skills: Expected array, received string"
skills: verify-before-trust, runtime-evidence

# Right — both hosts accept a sequence.
tools: Read, Grep, Glob
skills:
  - verify-before-trust
  - runtime-evidence
```

This fails asymmetrically, which is why it survives review. Claude Code
documents `skills` as a list but tolerates the string, so an agent authored and
tested only on Claude looks correct. GitHub Copilot CLI validates it as an
array, and a schema failure on one key discards *every* field — the agent loads
with empty metadata and never registers.

The damage is not a missing agent. A skill that dispatches it fails with "agent
type isn't registered", and the caller's natural recovery is to re-dispatch the
same instructions to a general-purpose worker. That silently discards the
agent's `tools` restriction, so a read-only reviewer becomes a worker that can
write. Prefer failing loudly over a fallback that quietly widens permissions.

`check-skills.sh` enforces the list shape through `scripts/agent_frontmatter.py`,
a peer of `command_frontmatter.py` that reuses the same standard-library YAML
type resolution rather than re-deriving it. It additionally rejects an empty
`skills`, a non-scalar item (`[[a]]` is an array of arrays, which Copilot also
refuses), and an entry naming a skill that does not exist in this repo, since a
preload the host skips leaves the agent running without the knowledge it was
built around. `scripts/test-agents.sh` covers those cases.

The existence check is monorepo-scoped on purpose: it asserts the skill exists
somewhere under `plugins/`, not that it ships in the agent's own plugin.
Cross-plugin preloads are legitimate — `context-handoff`'s agent preloads
`verify-before-trust` from `verify` — but they are only safe because the plugin
declares that dependency, which this gate does not check for you.
