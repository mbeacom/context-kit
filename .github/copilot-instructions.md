# Copilot instructions for productivity-skills

This repository is both a Claude Code plugin marketplace and a GitHub Copilot-compatible retrieval skill pack. The reusable value lives in `SKILL.md` files, their `references/` folders, and local CLI workflows.

- Keep `.claude-plugin/` manifests, Claude hooks, and `/plugin` install commands Claude-specific.
- Keep skill bodies portable across Claude Code and GitHub Copilot; pair any `CLAUDE_PLUGIN_*` example with a neutral `PRODUCTIVITY_SKILLS_*` equivalent when possible.
- GitHub Copilot CLI installs these plugins directly (`copilot plugin marketplace add mbeacom/productivity-skills`, then `copilot plugin install <name>@productivity-skills`); document that flow rather than manual skill-folder copying.
- APM (Agent Package Manager, `microsoft/apm`) installs the same plugins: `apm marketplace add mbeacom/productivity-skills`, then `apm install <name>@productivity-skills`. Each plugin ships a sibling `apm.yml` mirroring `plugin.json` (keep `name`/`version`/`description` in sync); do not regenerate `marketplace.json` with `apm pack` (it drops the `category` field). See `docs/APM.md`.
- Prefer `PRODUCTIVITY_SKILLS_DATA`, `PRODUCTIVITY_SKILLS_EMBED_MODEL`, `PRODUCTIVITY_SKILLS_OLLAMA_HOST`, and `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` in portable examples.
- Preserve the repo layout: plugin components live under `plugins/<name>/skills`, `plugins/<name>/agents`, and `plugins/<name>/scripts`; plugin manifests live under `.claude-plugin/`, and each plugin ships a sibling `plugins/<name>/apm.yml` (no `.apm/` directory, so the plugin-native layout stays authoritative).
- When running terminal checks, prefer `rtk` if installed for compact output, but avoid using rtk-filtered output as machine-readable input in pipes unless the command is documented as pipe-safe.

Useful validation commands:

```bash
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done
pre-commit run --all-files
cd plugins/local-rag && uv run --group dev pytest -q
```
