# Using productivity-skills with GitHub Copilot

`productivity-skills` is packaged as a Claude Code plugin marketplace, but the
important retrieval guidance is intentionally portable: the `SKILL.md` files,
their `references/` folders, and the CLI workflows work well as GitHub Copilot
Agent Skills too.

Claude Code still gets the first-class marketplace experience (`/plugin install`,
manifests, hooks, and plugin-scoped environment variables). GitHub Copilot users
can copy or symlink the same skill folders into Copilot's skill locations and run
the local CLIs directly.

## What is compatible

| Repository asset | Claude Code | GitHub Copilot |
| --- | --- | --- |
| `plugins/*/skills/<name>/SKILL.md` | Installed by the Claude plugin marketplace | Copy/symlink to `.github/skills/<name>/` or `~/.copilot/skills/<name>/` |
| `references/` folders next to a skill | Progressive skill resources | Keep them next to the copied `SKILL.md` |
| `plugins/retrieval-core/agents/retrieval-strategist.md` | Claude subagent | Adapt to `.github/agents/retrieval-strategist.agent.md` |
| `plugins/local-rag/bin/rag` | Auto-bootstrapped by a Claude `SessionStart` hook | Run `scripts/bootstrap.sh` manually and add `bin/` to `PATH` |
| `.claude-plugin/*` manifests | Claude-specific packaging | Not used by Copilot |

Copilot's discovery-critical skill frontmatter is `name` and `description`.
This repo's skill frontmatter keeps those fields compatible. If your Copilot
version flags extra metadata such as `allowed-tools`, keep the same body and
references but trim unknown frontmatter keys in your copied skill.

## Workspace install for GitHub Copilot

For a project-local setup shared with a team, copy the skills into `.github/skills`:

```bash
mkdir -p .github/skills
cp -R plugins/retrieval-core/skills/retrieval-strategy .github/skills/
cp -R plugins/code-search/skills/code-search .github/skills/
cp -R plugins/code-search/skills/data-and-docs-search .github/skills/
cp -R plugins/local-rag/skills/local-rag .github/skills/
cp -R plugins/obsidian/skills/obsidian-rag-bridge .github/skills/
```

Then ask Copilot naturally, for example:

- "Use the retrieval strategy to find where retry backoff is handled."
- "Use code-search to find structural React `useEffect` cleanup issues."
- "Use local-rag to query my notes for billing open questions."
- "Use the Obsidian RAG bridge to search notes linked to Project X."

## Personal install for GitHub Copilot

For a user-level setup that follows you across workspaces, copy or symlink the
same skill folders into `~/.copilot/skills/`:

```bash
mkdir -p ~/.copilot/skills
cp -R plugins/retrieval-core/skills/retrieval-strategy ~/.copilot/skills/
cp -R plugins/code-search/skills/code-search ~/.copilot/skills/
cp -R plugins/code-search/skills/data-and-docs-search ~/.copilot/skills/
cp -R plugins/local-rag/skills/local-rag ~/.copilot/skills/
cp -R plugins/obsidian/skills/obsidian-rag-bridge ~/.copilot/skills/
```

Use symlinks instead of copies if you want a local clone of this repository to be
the source of truth while you iterate on the skills.

## Optional Copilot custom agent

The `retrieval-strategist` agent is read-only and ports cleanly to a Copilot
custom agent. Copy the body from
`plugins/retrieval-core/agents/retrieval-strategist.md` into
`.github/agents/retrieval-strategist.agent.md`, then use Copilot-style
frontmatter such as:

```yaml
---
name: Retrieval Strategist
description: "Use for open-ended retrieval questions that may need lexical, structural, history, semantic/RAG, or graph search."
tools: [read, search, execute]
---
```

Remove Claude-only fields like `skills:` from the copied frontmatter. Keep the
body instruction that the agent should consult the `retrieval-strategy` skill;
Copilot can load that skill when it is installed in `.github/skills/` or
`~/.copilot/skills/`.

## Running local-rag outside Claude Code

Claude Code runs `plugins/local-rag/scripts/bootstrap.sh` automatically and sets
`CLAUDE_PLUGIN_DATA`. Copilot/manual users should choose a neutral data location,
bootstrap the venv, and put `rag` on `PATH`:

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
working. The `PRODUCTIVITY_SKILLS_*` names are preferred for portable docs,
Copilot setups, and shell profiles shared across agents.

## Tooling expectations

Copilot does not install the underlying CLI tools for you. Install the same tools
the Claude skills expect:

- Required for `code-search`: `rg` (ripgrep).
- Optional but useful: `fd`, `ast-grep`/`sg`, `semgrep`, `jq`, `yq`, `gron`,
  `duckdb`, `sqlite-utils`, `rga`, `pandoc`, `pdftotext`, `difftastic`, `tokei`,
  `scc`, and `rtk`.
- Required for `local-rag`: `uv`, `ollama`, and an embedding model such as
  `nomic-embed-text`.
- Optional for `obsidian-rag-bridge`: the official `obsidian` CLI with Obsidian
  running; otherwise use the `rg`/`fd` fallback over vault files.

Run `plugins/code-search/scripts/check-tools.sh` from this repository to see what
is already installed and what `brew install ...` command would fill the gaps.

## Authoring portable skills

When updating this repo, keep the reusable retrieval instructions agent-neutral:

1. Put cross-agent workflow knowledge in `SKILL.md` and `references/`.
2. Keep Claude marketplace mechanics in `.claude-plugin/`, hooks, and Claude-only docs.
3. Prefer `PRODUCTIVITY_SKILLS_*` in portable examples, with `CLAUDE_PLUGIN_*`
   documented as the Claude fallback.
4. Mention when a behavior is installed automatically by Claude but must be run
   manually for GitHub Copilot.
5. Keep command output compact when possible (`rtk` is optional and safe to omit).
