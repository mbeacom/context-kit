# Using context-kit with APM (Agent Package Manager)

[APM](https://github.com/microsoft/apm) is Microsoft's open-source dependency
manager for AI coding agents — the `package.json`/`Cargo.toml` of agent context.
It installs the **same plugins** this repo publishes for GitHub Copilot and
Claude Code, adds a committed lockfile, audit/policy checks, transitive
dependency resolution, and cross-harness deployment, and works across Claude
Code, Copilot, Cursor, Codex, Gemini, Windsurf, Kiro, and OpenCode from one
registration.

APM reads the repo's `.claude-plugin/marketplace.json` directly (the
Anthropic-compatible schema every runtime shares) and consumes each plugin's
native layout as a **plugin collection** — no repo restructuring, no `.apm/`
directory. Each plugin also ships a small `apm.yml` that carries APM-native
metadata and dependencies.

## Install for APM

Register this marketplace, then install the plugins you want. The marketplace
name defaults to the repo name, `context-kit`:

```bash
apm marketplace add mbeacom/context-kit
apm install code-search@context-kit      # also pulls retrieval-core (the spine)
apm install local-rag@context-kit
apm install obsidian@context-kit
apm install plan-execute@context-kit
apm install context-steering@context-kit
apm install verify@context-kit           # also pulls retrieval-core
apm install runtime-evidence@context-kit # pulls verify, then retrieval-core
apm install context-handoff@context-kit  # pulls verify, then retrieval-core
apm install memory@context-kit           # pulls handoff, verify, retrieval-core
apm install plugin-forge@context-kit
```

Installing `code-search` deploys the retrieval spine automatically: its
`apm.yml` declares a dependency on `retrieval-core`, so APM also lands the
`retrieval-strategist` agent and the `retrieval-strategy` skill. (This mirrors
the plugin.json `"dependencies": ["retrieval-core"]` that Claude Code and
Copilot honor — APM does not read that Claude field, so the plugin declares the
dependency in its `apm.yml`.)

`runtime-evidence` and `context-handoff` each declare an APM dependency on
`verify`. Installing either therefore deploys `verify` and, transitively,
`retrieval-core`. `memory` declares a dependency on `context-handoff`, so its
full continuity/verification chain is installed too.

Prefer `apm install` over a runtime's native install when a team or CI uses the
plugins: it is the only path that writes a project-scoped `apm.lock.yaml`, pins
content hashes, resolves transitive dependencies, and participates in
`apm audit --ci` drift detection.

### Install a single plugin without registering the marketplace

Each plugin directory is also a virtual subdirectory package, so you can install
one straight from the repo:

```bash
apm install mbeacom/context-kit/plugins/code-search
```

## Where files land, and picking a target

`apm install` auto-detects which agent harnesses your project uses and deploys
to all of them (`.claude/`, `.github/`, `.cursor/`, `.codex/`, `.gemini/`, …),
plus the cross-tool `.agents/skills/`. Pin a target for reproducibility:

```bash
apm install code-search@context-kit --target claude
apm install code-search@context-kit --target copilot,cursor
```

The retrieval `SKILL.md` bodies, their `references/`, and the agents are
identical across harnesses — only the deployment directory differs.

Inspect and maintain what you installed:

```bash
apm list                     # scripts declared in your apm.yml
apm view code-search         # details for one installed package
apm audit                    # re-hash deployed files; catch drift
apm update                   # refresh to the latest matching refs
```

## Running local-rag under APM

`local-rag`'s `rag` CLI runs on a uv-managed virtualenv. Claude Code bootstraps
it automatically via a `SessionStart` hook; **APM does not run Claude hooks**
(the same limitation as GitHub Copilot), so bootstrap it once yourself from a
clone of this repo, exactly as in
[docs/GITHUB_COPILOT.md](GITHUB_COPILOT.md):

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
ollama pull nomic-embed-text
rag index /path/to/vault --name notes
rag query "open questions about billing" --name notes --k 8
```

APM plugins have no Claude-style `userConfig`, so configure `local-rag` and
`obsidian` with the portable environment variables (documented in
[docs/GITHUB_COPILOT.md](GITHUB_COPILOT.md#running-local-rag-outside-claude-code)):

| Variable | Purpose | Claude fallback |
| --- | --- | --- |
| `CONTEXT_KIT_DATA` | venv and index storage for `local-rag` | `CLAUDE_PLUGIN_DATA` |
| `CONTEXT_KIT_EMBED_MODEL` | ollama embedding model | `CLAUDE_PLUGIN_OPTION_EMBED_MODEL` |
| `CONTEXT_KIT_OLLAMA_HOST` | ollama base URL | `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` |
| `CONTEXT_KIT_OBSIDIAN_VAULT` | vault path for `obsidian` examples/fallbacks | `CLAUDE_PLUGIN_OPTION_VAULT_PATH` |
| `CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG` | user-owned exact-ID JSON command allowlist | — |
| `CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT` | installed runtime-evidence root | `CLAUDE_PLUGIN_ROOT` |
| `CONTEXT_KIT_HANDOFF_PATH` | handoff artifact override | — |
| `CONTEXT_KIT_MEMORY_PROVIDER` | `none` or optional `mempalace` provider | `CLAUDE_PLUGIN_OPTION_PROVIDER` |
| `CONTEXT_KIT_MEMORY_HOME` | reviewed records and project-isolated provider data | `CLAUDE_PLUGIN_OPTION_MEMORY_HOME` |
| `CONTEXT_KIT_MEMORY_PROJECT` | explicit durable-memory project scope | `CLAUDE_PLUGIN_OPTION_PROJECT` |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | opt-in Claude lifecycle forwarding | `CLAUDE_PLUGIN_OPTION_AUTO_CAPTURE` |
| `CONTEXT_KIT_MEMORY_ROOT` | installed memory plugin root | `CLAUDE_PLUGIN_ROOT` |

The pre-rename `PRODUCTIVITY_SKILLS_*` names still work as a deprecated alias
(`CONTEXT_KIT_*` → `PRODUCTIVITY_SKILLS_*` → Claude fallback).

## Tooling expectations

APM installs the plugins, not the CLI tools they drive. Install the same tools
listed in [docs/GITHUB_COPILOT.md](GITHUB_COPILOT.md#tooling-expectations):
`rg` (required for `code-search`); `uv` + `ollama` + an embedding model
(required for `local-rag`); the rest optional. Run
`plugins/code-search/scripts/check-tools.sh` from a clone to see the gaps.
Python 3 is required for the stdlib `runtime-evidence` runner and
`context-handoff` validator. The runtime runner requires POSIX and refuses
Windows before execution; the handoff validator is cross-platform.
The `memory` adapter also uses Python 3; MemPalace is a separately installed
optional provider. APM does not execute Claude hooks, so memory capture remains
explicit unless the target host is configured separately.

## For maintainers

- **`.claude-plugin/marketplace.json` stays hand-authored.** APM can *generate*
  it from a root `apm.yml` marketplace block via `apm pack`, but that output
  drops the per-plugin `category` field (APM emits `category` only for Codex
  output) and rewrites the file. This repo keeps the catalog hand-authored so
  Claude Code, Copilot, and APM all read the same, category-tagged artifact — do
  not run `apm pack` to regenerate it. The category-drop is fixed upstream by
  [microsoft/apm#2189](https://github.com/microsoft/apm/pull/2189) (merged,
  unreleased as of 2026-07); once it ships, generated output *may* preserve
  `category`, but before relaxing this rule still confirm `apm pack` doesn't churn
  ordering/formatting and doesn't list unshipped plugins (the catalog lists only
  shipped ones).
- **Each plugin's `apm.yml` mirrors its `plugin.json`.** Keep `name` and
  `version` strictly in sync when you bump a plugin; `description` is
  intentionally a more concise variant tuned for APM/CLI listings (the
  `plugin.json` copy stays fuller). There is no `.apm/` directory, so the
  plugin-native layout remains the source of truth.
- **Inter-plugin dependencies use local sibling paths.** `code-search` and
  `verify` pull `retrieval-core`; `runtime-evidence` and `context-handoff` pull
  `verify`, which transitively pulls the spine; `memory` pulls
  `context-handoff`. For example, `code-search` uses
  `- path: ../retrieval-core`. `apm install code-search@context-kit`
  resolves it and deploys the spine. If you then install *another* plugin in the
  same project, APM re-reads code-search's manifest and logs a benign
  `Invalid transitive apm.yml … Invalid APM dependency 'retrieval-core'`
  warning — a known APM quirk with local-path deps. It is non-fatal (the spine is
  already deployed and the later install still succeeds); do not "fix" it by
  hardcoding the GitHub `owner/repo` path, which would break forks and local
  installs.
- **Validate** the APM side with `apm marketplace add ./ --name ps` against a
  clone plus a scratch `apm install <plugin>@ps`, and the Claude side with
  `claude plugin validate ./plugins/<name> --strict` (an `apm.yml` beside
  `plugin.json` does not affect Claude validation).

## Where next

- [Home](index.md) — the plugin catalog and GitHub Copilot / APM / Claude Code install.
- [docs/GITHUB_COPILOT.md](GITHUB_COPILOT.md) — the shared portable-config and
  `local-rag` bootstrap notes APM reuses.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — the retrieval-modality model.
