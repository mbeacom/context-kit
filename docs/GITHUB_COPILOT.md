# Using productivity-skills with GitHub Copilot

`productivity-skills` is a plugin marketplace that both Claude Code and GitHub
Copilot CLI install from **directly** — the same plugins, from a single Markdown
source. No manual copying of skill folders.

Claude Code installs via `/plugin`; GitHub Copilot CLI installs via
`copilot plugin`. The retrieval `SKILL.md` bodies, their `references/`, the agents,
and the commands are identical across hosts.

## Install for GitHub Copilot

Register this marketplace, then install the plugins you want:

```bash
copilot plugin marketplace add mbeacom/productivity-skills
copilot plugin install code-search@productivity-skills      # auto-installs retrieval-core
copilot plugin install local-rag@productivity-skills
copilot plugin install obsidian@productivity-skills
```

Manage them with `copilot plugin list`, `copilot plugin update <name>`, and
`copilot plugin uninstall <name>`.

## What you get

| Repository asset | Claude Code | GitHub Copilot |
| --- | --- | --- |
| `plugins/*/skills/<name>/SKILL.md` (+ `references/`) | Installed via `/plugin install` | Installed via `copilot plugin install` |
| `plugins/retrieval-core/agents/retrieval-strategist.md` | Installed as a subagent | Installed with the plugin |
| `plugins/local-rag/bin/rag` | Auto-bootstrapped by a Claude `SessionStart` hook | Bootstrap manually — see below |
| `.claude-plugin/*` manifests | Marketplace packaging | Used to resolve the marketplace |

Copilot's discovery-critical skill frontmatter is `name` and `description`, which
this repo's skills keep compatible.

## Using the skills

Once installed, ask Copilot naturally, for example:

- "Use the retrieval strategy to find where retry backoff is handled."
- "Use code-search to find structural React `useEffect` cleanup issues."
- "Use local-rag to query my notes for billing open questions."
- "Use the Obsidian RAG bridge to search notes linked to Project X."

## Running local-rag outside Claude Code

`local-rag`'s `rag` CLI runs on a uv-managed venv. Claude Code bootstraps it
automatically via a `SessionStart` hook; GitHub Copilot does not run Claude hooks,
so bootstrap it once yourself from a clone of this repo:

```bash
export PRODUCTIVITY_SKILLS_DATA="$HOME/.local/share/productivity-skills/local-rag"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
ollama pull nomic-embed-text
rag index /path/to/vault --name notes
rag query "open questions about billing" --name notes --k 8
```

Supported neutral environment variables:

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `PRODUCTIVITY_SKILLS_DATA` | venv and index storage for `local-rag` | `CLAUDE_PLUGIN_DATA` |
| `PRODUCTIVITY_SKILLS_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `PRODUCTIVITY_SKILLS_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |
| `PRODUCTIVITY_SKILLS_OBSIDIAN_VAULT` | vault path used by examples/fallbacks | `CLAUDE_PLUGIN_OPTION_VAULT_PATH` |

The Claude-specific variables remain supported so existing plugin installs keep
working. The `PRODUCTIVITY_SKILLS_*` names are preferred for portable docs and
shell profiles shared across agents.

## Tooling expectations

Neither host installs the underlying CLI tools for you. Install the same tools the
skills expect:

- Required for `code-search`: `rg` (ripgrep).
- Optional but useful: `fd`, `ast-grep`/`sg`, `semgrep`, `jq`, `yq`, `gron`,
  `duckdb`, `sqlite-utils`, `rga`, `pandoc`, `pdftotext`, `difftastic`, `tokei`,
  `scc`, and `rtk`.
- Required for `local-rag`: `uv`, `ollama`, and an embedding model such as
  `nomic-embed-text`.
- Optional for `obsidian-rag-bridge`: the official `obsidian` CLI with Obsidian
  running; otherwise use the `rg`/`fd` fallback over vault files.

Run `plugins/code-search/scripts/check-tools.sh` from a clone of this repository to
see what is already installed and what `brew install ...` command would fill the gaps.

## Authoring portable skills

When updating this repo, keep the reusable retrieval instructions agent-neutral:

1. Put cross-agent workflow knowledge in `SKILL.md` and `references/`.
2. Keep Claude marketplace mechanics in `.claude-plugin/`, hooks, and Claude-only docs.
3. Prefer `PRODUCTIVITY_SKILLS_*` in portable examples, with `CLAUDE_PLUGIN_*`
   documented as the Claude fallback.
4. Mention when a behavior is installed automatically by Claude (for example, the
   `local-rag` bootstrap hook) but must be run manually for GitHub Copilot.
5. Keep command output compact when possible (`rtk` is optional and safe to omit).
