# AGENTS.md

Portable, always-on guidance for any coding agent — GitHub Copilot CLI, APM,
Claude Code, and other `AGENTS.md`-aware tools — working in **context-kit**.
Host-specific notes live in [`CLAUDE.md`](CLAUDE.md) (Claude Code) and
[`.github/copilot-instructions.md`](.github/copilot-instructions.md) (GitHub
Copilot); this file holds the rules shared across all hosts.

## What this repo is

A multi-host plugin marketplace for **context engineering** — retrieval
modalities plus a routing agent, hybrid local RAG, an Obsidian bridge,
provenance-bound durable memory, plan-big/execute-small orchestration, context
steering, read-only verification, controlled runtime evidence, cross-session
handoff, and portable plugin authoring. It is a catalog of plugins/skills, not
an application. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Layout

- `.claude-plugin/marketplace.json` — hand-authored catalog; lists shipped plugins only.
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/apm.yml` — APM manifest mirroring `plugin.json`.
- `plugins/<name>/skills/<name>/SKILL.md` — skills (+ `references/` for detail).
- `plugins/<name>/agents/<name>.md` — subagents.
- Component dirs (`skills/`, `agents/`, `commands/`, `scripts/`, `hooks/`) live at
  the plugin root — never inside `.claude-plugin/`, which holds only `plugin.json`.

## Rules that always apply

- **Manifest sync:** keep `plugin.json` and `apm.yml` `name`/`version` strictly
  identical. `version` is Claude Code's cache key — bump both together to ship.
- **Discovery frontmatter:** every `SKILL.md`/agent needs a `name` matching its
  directory/file and a `description` that starts with a trigger ("Use when …").
  Both hosts decide when to load a component from these two fields.
- **Portable env vars:** prefer `CONTEXT_KIT_*` (e.g. `CONTEXT_KIT_DATA`) and
  document `CLAUDE_PLUGIN_*` as the Claude fallback. Use `${CLAUDE_PLUGIN_ROOT}`
  for in-plugin paths; never hardcode install locations.
- **Skill granularity:** a few well-scoped skills with `references/` beat many
  tiny ones — always-on name+description cost scales with skill count.
- **Catalog discipline:** add a `marketplace.json` entry only when a plugin is
  ready to ship; keep it hand-authored (never `apm pack`, which drops `category`).
- **Fresh content, MIT (Mark Beacom):** don't copy externally licensed text.

## Validate before shipping

```bash
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done
bash plugins/plugin-forge/scripts/check-manifests.sh   # plugin.json ⇆ apm.yml drift
bash plugins/plugin-forge/scripts/check-skills.sh      # skill/agent discovery frontmatter
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
pre-commit run --all-files                             # markdownlint + shellcheck + ruff + these checks
python3 -m unittest discover -s plugins/runtime-evidence/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/context-handoff/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/memory/tests -p 'test_*.py'
python3 -m unittest discover -s tests/integration -p 'test_*.py'
cd plugins/local-rag && uv run --group dev pytest -q   # local-rag Python tests
```
