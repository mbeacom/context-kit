# Copilot instructions for context-kit

This repository is both a Claude Code plugin marketplace and a GitHub
Copilot-compatible context-engineering skill pack. The reusable value lives in
`SKILL.md` files, their `references/` folders, and local CLI workflows.

Shared, host-neutral rules (layout, manifest sync, discovery frontmatter, portable env vars, validation commands) live in [`AGENTS.md`](../AGENTS.md); the Copilot-specific notes below build on them.

- Keep `.claude-plugin/` manifests, Claude hooks, and `/plugin` install commands Claude-specific.
- Keep skill bodies portable across Claude Code and GitHub Copilot; pair any `CLAUDE_PLUGIN_*` example with a neutral `CONTEXT_KIT_*` equivalent when possible.
- GitHub Copilot CLI installs these plugins directly (`copilot plugin marketplace add mbeacom/context-kit`, then `copilot plugin install <name>@context-kit`); document that flow rather than manual skill-folder copying.
- APM (Agent Package Manager, `microsoft/apm`) installs the same plugins: `apm marketplace add mbeacom/context-kit`, then `apm install <name>@context-kit`. Each plugin ships a sibling `apm.yml` mirroring `plugin.json` (keep `name`/`version` strictly in sync; `description` is intentionally a more concise variant tuned for APM/CLI listings); do not regenerate `marketplace.json` with `apm pack` (it drops the `category` field). See `docs/APM.md`.
- Prefer `CONTEXT_KIT_DATA`, `CONTEXT_KIT_EMBED_MODEL`, `CONTEXT_KIT_OLLAMA_HOST`, and `CONTEXT_KIT_OBSIDIAN_VAULT` in portable examples.
- For durable memory, prefer `CONTEXT_KIT_MEMORY_*`; keep MemPalace optional,
  project-scoped, and separately installed. Copilot does not run Claude hooks.
- Preserve the repo layout: plugin components live under `plugins/<name>/skills`, `plugins/<name>/agents`, and `plugins/<name>/scripts`; plugin manifests live under `.claude-plugin/`, and each plugin ships a sibling `plugins/<name>/apm.yml` (no `.apm/` directory, so the plugin-native layout stays authoritative).
- When running terminal checks, prefer `rtk` if installed for compact output, but avoid using rtk-filtered output as machine-readable input in pipes unless the command is documented as pipe-safe.

Useful validation commands:

```bash
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done
bash plugins/plugin-forge/scripts/check-manifests.sh
bash plugins/plugin-forge/scripts/check-skills.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
pre-commit run --all-files
python3 -m unittest discover -s plugins/runtime-evidence/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/context-handoff/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/memory/tests -p 'test_*.py'
cd plugins/local-rag && uv run --group dev pytest -q
```
