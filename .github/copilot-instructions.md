# Copilot instructions for productivity-skills

This repository is both a Claude Code plugin marketplace and a GitHub Copilot-compatible retrieval skill pack. The reusable value lives in `SKILL.md` files, their `references/` folders, and local CLI workflows.

- Keep `.claude-plugin/` manifests, Claude hooks, and `/plugin` install commands Claude-specific.
- Keep skill bodies portable across Claude Code and GitHub Copilot; pair any `CLAUDE_PLUGIN_*` example with a neutral `PRODUCTIVITY_SKILLS_*` equivalent when possible.
- For Copilot documentation, point workspace skills at `.github/skills/<name>/`, personal skills at `~/.copilot/skills/<name>/`, and custom agents at `.github/agents/*.agent.md`.
- Prefer `PRODUCTIVITY_SKILLS_DATA`, `PRODUCTIVITY_SKILLS_EMBED_MODEL`, `PRODUCTIVITY_SKILLS_OLLAMA_HOST`, and `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` in portable examples.
- Preserve the repo layout: plugin components live under `plugins/<name>/skills`, `plugins/<name>/agents`, and `plugins/<name>/scripts`; only plugin manifests live under `.claude-plugin/`.
- When running terminal checks, prefer `rtk` if installed for compact output, but avoid using rtk-filtered output as machine-readable input in pipes unless the command is documented as pipe-safe.

Useful validation commands:

```bash
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done
pre-commit run --all-files
cd plugins/local-rag && uv run --group dev pytest -q
```
