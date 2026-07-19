# Using context-kit with GitHub Copilot

`context-kit` is a plugin marketplace that GitHub Copilot CLI installs from
**directly** — the same plugins Claude Code and APM use, from one shared source.
No manual copying of skill folders.

GitHub Copilot CLI installs via `copilot plugin`; Claude Code installs via
`/plugin` and APM via `apm install`. The retrieval `SKILL.md` bodies, their
`references/`, the agents, and the commands are identical across hosts.

## Install for GitHub Copilot

Register this marketplace, then install the plugins you want:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install code-search@context-kit      # auto-installs retrieval-core
copilot plugin install local-rag@context-kit
copilot plugin install obsidian@context-kit
copilot plugin install plan-execute@context-kit
copilot plugin install context-steering@context-kit
copilot plugin install verify@context-kit           # auto-installs retrieval-core
copilot plugin install runtime-evidence@context-kit # pulls verify, then retrieval-core
copilot plugin install context-handoff@context-kit  # pulls verify, then retrieval-core
copilot plugin install memory@context-kit           # pulls handoff, verify, retrieval-core
copilot plugin install plugin-forge@context-kit
```

`runtime-evidence` and `context-handoff` depend on `verify`; `verify`
transitively pulls `retrieval-core`. `memory` depends on `context-handoff`.

Manage them with `copilot plugin list`, `copilot plugin update <name>`, and
`copilot plugin uninstall <name>`.

## What you get

| Repository asset | GitHub Copilot | Claude Code |
| --- | --- | --- |
| `plugins/*/skills/<name>/SKILL.md` (+ `references/`) | Installed via `copilot plugin install` | Installed via `/plugin install` |
| `plugins/retrieval-core/agents/retrieval-strategist.md` | Installed with the plugin | Installed as a subagent |
| `plugins/local-rag/bin/rag` | Bootstrap manually — see below | Auto-bootstrapped by a Claude `SessionStart` hook |
| `plugins/memory/scripts/memory-provider.py` | Run explicitly; Copilot does not run Claude hooks | Explicit commands plus opt-in Claude hooks |
| `.claude-plugin/*` manifests | Used to resolve the marketplace | Marketplace packaging |

Copilot's discovery-critical skill frontmatter is `name` and `description`, which
this repo's skills keep compatible.

## Using the skills

Once installed, ask Copilot naturally, for example:

- "Use the retrieval strategy to find where retry backoff is handled."
- "Use code-search to find structural React `useEffect` cleanup issues."
- "Use local-rag to query my notes for billing open questions."
- "Use the Obsidian RAG bridge to search notes linked to Project X."
- "Analyze the prospective impact of changing this schema."
- "Collect bounded runtime evidence for this unable-to-check claim."
- "Write a context handoff for the next session."
- "Recall why this project changed its retry policy, then verify current evidence."

## Running local-rag outside Claude Code

`local-rag`'s `rag` CLI runs on a uv-managed venv. Claude Code bootstraps it
automatically via a `SessionStart` hook; GitHub Copilot does not run Claude hooks,
so bootstrap it once yourself from a clone of this repo:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit/local-rag"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
ollama pull nomic-embed-text
rag index /path/to/vault --name notes
rag query "open questions about billing" --name notes --k 8
rag query "open questions about billing" --name notes --k 8 --hybrid
```

Supported neutral environment variables:

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage for `local-rag` | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |
| `CONTEXT_KIT_OBSIDIAN_VAULT` | vault path used by examples/fallbacks | `CLAUDE_PLUGIN_OPTION_VAULT_PATH` |
| `CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG` | user-owned exact-ID JSON command allowlist | — |
| `CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT` | installed runtime-evidence root | `CLAUDE_PLUGIN_ROOT` |
| `CONTEXT_KIT_HANDOFF_PATH` | handoff artifact override | — |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none` or optional `mempalace` provider | `CLAUDE_PLUGIN_OPTION_PROVIDER` |
| `CONTEXT_KIT_MEMORY_HOME` | reviewed records and project-isolated provider data | `CLAUDE_PLUGIN_OPTION_MEMORY_HOME` |
| `CONTEXT_KIT_MEMORY_PROJECT` | explicit durable-memory project scope | `CLAUDE_PLUGIN_OPTION_PROJECT` |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | opt-in Claude lifecycle forwarding | `CLAUDE_PLUGIN_OPTION_AUTO_CAPTURE` |
| `CONTEXT_KIT_MEMORY_ROOT` | installed memory plugin root | `CLAUDE_PLUGIN_ROOT` |

The Claude-specific variables remain supported so existing plugin installs keep
working. The `CONTEXT_KIT_*` names are preferred for portable docs and
shell profiles shared across agents. The former `PRODUCTIVITY_SKILLS_*` names
(from before the marketplace was renamed to `context-kit`) are still honored as a
deprecated alias — resolution order is `CONTEXT_KIT_*` → `PRODUCTIVITY_SKILLS_*` →
the Claude fallback — but will be dropped in a future release; migrate when convenient.

## Tooling expectations

Neither host installs the underlying CLI tools for you. Install the same tools the
skills expect:

- Required for `code-search`: `rg` (ripgrep).
- Optional but useful: `fd`, `ast-grep`/`sg`, `semgrep`, `jq`, `yq`, `gron`,
  `duckdb`, `sqlite-utils`, `rga`, `pandoc`, `pdftotext`, `difftastic`, `tokei`,
  `scc`, and `rtk`.
- Required for `local-rag`: `uv`, `ollama`, and an embedding model such as
  `nomic-embed-text`. SQLite FTS5 is required only for opt-in `--hybrid`; the
  default semantic mode remains available without it.
- Required for `runtime-evidence` and `context-handoff`: Python 3. Their runner
  and validator use only the standard library. The runtime runner requires POSIX
  and refuses Windows before execution; the handoff validator is cross-platform.
  Copilot does not provide universal host-level command enforcement; runtime
  collection remains bound to the plugin's reviewed exact-ID allowlist.
- Optional for `obsidian-rag-bridge`: the official `obsidian` CLI with Obsidian
  running; otherwise use the `rg`/`fd` fallback over vault files.
- Required for local `memory` records: Python 3. Optional provider recall uses a
  separately installed `mempalace` CLI. Copilot does not run the plugin's Claude
  lifecycle hooks, so capture remains explicit unless a native host integration
  is configured separately.

Run `plugins/code-search/scripts/check-tools.sh` from a clone of this repository to
see what is already installed and what `brew install ...` command would fill the gaps.

## Authoring portable skills

When updating this repo, keep the reusable retrieval instructions agent-neutral:

1. Put cross-agent workflow knowledge in `SKILL.md` and `references/`.
2. Keep Claude marketplace mechanics in `.claude-plugin/`, hooks, and Claude-only docs.
3. Prefer `CONTEXT_KIT_*` in portable examples, with `CLAUDE_PLUGIN_*`
   documented as the Claude fallback.
4. Mention when a behavior is installed automatically by Claude (for example, the
   `local-rag` bootstrap hook) but must be run manually for GitHub Copilot.
5. Keep command output compact when possible (`rtk` is optional and safe to omit).
