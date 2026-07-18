# Contributing

`context-kit` is a Claude Code **plugin marketplace** and a Copilot/APM-compatible
Agent Skills pack — a catalog of plugins, not an application. The reusable value
lives in `SKILL.md` files, their `references/`, subagents, and local CLI
workflows.

## Repository layout

| Path | Purpose |
| --- | --- |
| `.claude-plugin/marketplace.json` | The catalog (hand-authored; lists shipped plugins only). |
| `plugins/<name>/.claude-plugin/plugin.json` | Per-plugin manifest (Claude Code + Copilot). |
| `plugins/<name>/apm.yml` | Per-plugin APM manifest, mirroring `plugin.json`. |
| `plugins/<name>/skills/<name>/SKILL.md` | Skills, with `references/*.md` for detail. |
| `plugins/<name>/agents/<name>.md` | Subagents. |
| `docs/` | This documentation site (MkDocs Material). |

Component directories (`skills/`, `agents/`, `scripts/`) live at the **plugin
root**, never inside `.claude-plugin/` (that dir holds only `plugin.json`).

## Validate, lint, and test

```bash
# Validate the marketplace + every plugin
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done

# Lint everything (markdownlint + shellcheck + ruff + hygiene)
pre-commit run --all-files

# Run the local-rag Python tests
cd plugins/local-rag && uv run --group dev pytest -q
```

CI (`.github/workflows/validate.yml`) runs `claude plugin validate --strict` on
every plugin, `pre-commit`, and the `local-rag` pytest suite.

## Build the docs locally

The site is [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). Serve
it with live reload, or build a static copy:

```bash
# Live preview at http://127.0.0.1:8000
uv run --with-requirements docs/requirements.txt mkdocs serve

# Production build (strict: fail on broken links / nav)
uv run --with-requirements docs/requirements.txt mkdocs build --strict
```

The `main` branch deploys to GitHub Pages automatically via
`.github/workflows/docs.yml`. The build output (`/site`) is git-ignored.

## Conventions

- **Adding a plugin** — create `plugins/<name>/.claude-plugin/plugin.json`, add
  `skills/`/`agents/`, add a sibling `apm.yml`, and a `LICENSE` + `CHANGELOG.md`.
  Add the `marketplace.json` catalog entry **only when the plugin is ready** —
  stubs stay unlisted so they can't be installed half-built. Add a page here under
  `docs/plugins/` and wire it into `mkdocs.yml`.
- **Versioning** — bump `version` in `plugin.json` to ship updates (Claude Code
  uses it as the cache key). Bump the matching `apm.yml` `version` in lockstep;
  `plugin-forge`'s `check-manifests.sh` enforces this.
- **Portability** — keep skill bodies host-neutral. Prefer `CONTEXT_KIT_*`
  environment variables in examples, with `CLAUDE_PLUGIN_*` documented as the
  Claude fallback. Keep marketplace mechanics in `.claude-plugin/` and Claude-only
  docs.
- **Licensing** — repo and all plugins are MIT (Mark Beacom). Content is written
  fresh; do not copy text from externally licensed sources.
- **Markdown** — `.markdownlint-cli2.jsonc` disables MD013/MD033/MD041/MD060. Fix
  real lint findings rather than disabling more rules.

See [`CLAUDE.md`](https://github.com/mbeacom/context-kit/blob/main/CLAUDE.md) and
[`.github/copilot-instructions.md`](https://github.com/mbeacom/context-kit/blob/main/.github/copilot-instructions.md)
for the full contributor guide.
