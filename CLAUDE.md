# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`productivity-skills` is a **Claude Code plugin marketplace** (not an application).
It is a catalog of plugins, organized around **retrieval modalities** —
complementary ways an agent finds information (lexical, structural,
structured-data, history, semantic/RAG, graph), selected by what's known about
the query and corpus, and composed together. See `docs/ARCHITECTURE.md` for the
modality model.

## Layout

- `.claude-plugin/marketplace.json` — the catalog. **Lists only shipped plugins.**
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/skills/<name>/SKILL.md` — skills (with `references/*.md` for
  progressive-disclosure detail).
- `plugins/<name>/agents/<name>.md` — subagents.
- Component dirs (`skills/`, `agents/`, `scripts/`) live at the **plugin root**,
  never inside `.claude-plugin/` (that dir holds only `plugin.json`).

### Plugins

- `retrieval-core` — the spine: the `retrieval-strategist` agent + the
  `retrieval-strategy` decision-flow skill that pick/compose modalities.
- `code-search` — lexical/structural/structured-data/history/rewrite/metrics/doc
  search (two skills: `code-search` and `data-and-docs-search`). Declares
  `dependencies: ["retrieval-core"]`, so installing it pulls the spine.
- `local-rag` — fully-local semantic RAG. A `bin/rag` CLI (Python package under
  `src/local_rag/`, run via a uv venv bootstrapped into `${CLAUDE_PLUGIN_DATA}` by
  a `SessionStart` hook) that chunks → embeds via `ollama` → indexes with
  `turbovec`. All turbovec usage is isolated to `src/local_rag/index.py`.
- `obsidian` — a **skill-only** RAG bridge (no code/deps): vault graph/tags
  (official `obsidian` CLI, or `rg` fallback) → `rag query --allowlist`. Authoring
  / Bases / Canvas are out of scope (defer to `kepano/obsidian-skills`).

## Commands

- Validate one plugin: `claude plugin validate ./plugins/<name> --strict`
- Validate all plugins:
  `for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done`
- Lint everything (markdownlint + shellcheck + hygiene): `pre-commit run --all-files`
- Report which search CLIs are installed: `bash plugins/code-search/scripts/check-tools.sh`
  (a non-zero exit listing `brew install …` for missing optional tools is expected, not a failure).
- Run the `local-rag` Python tests: `cd plugins/local-rag && uv run --group dev pytest -q`
  (uv resolves a dev venv; no live ollama needed — the embed client is mocked, turbovec is exercised for real).
- Rebuild the `local-rag` runtime venv manually: `bash plugins/local-rag/scripts/bootstrap.sh`
  (normally automatic on `SessionStart`; it reinstalls only when `pyproject.toml` changes).

CI (`.github/workflows/validate.yml`) runs `claude plugin validate --strict` on
every plugin, `pre-commit`, and the `local-rag` pytest suite (the Linux runner
preloads OpenBLAS so `turbovec` imports). `local-rag` Python sources are linted
with `ruff` via pre-commit.

## Conventions when modifying this repo

- **Adding a plugin:** create `plugins/<name>/.claude-plugin/plugin.json` (include
  `$schema`, `name`, `displayName`, `version`, `description`, `author`,
  `homepage`/`repository`, `license`, `keywords`), add `skills/`/`agents/`, add a
  `LICENSE` + `CHANGELOG.md`. Add a catalog entry to `marketplace.json` **only
  when the plugin is ready** — stubs stay unlisted so they can't be installed
  half-built.
- **Versioning:** bump `version` in `plugin.json` to ship updates — Claude Code
  uses it as the cache key, so pushing commits without a bump ships nothing.
- **Licensing:** repo and all plugins are MIT (Mark Beacom). Each plugin ships
  its own `LICENSE`. Content is written fresh; do not copy text from externally
  licensed sources (e.g. the CC-BY-SA upstream that inspired `code-search`).
- **Skill granularity:** prefer few well-scoped skills with `references/` for
  detail over many fine-grained skills (always-on token cost scales with skill
  count). `code-search` uses two skills split by corpus (code vs data/docs).
- **Markdown:** `.markdownlint-cli2.jsonc` disables MD013/MD033/MD041/MD060.
  Fix real lint findings rather than disabling more rules.

## Environment note

A `PreToolUse` security hook on some machines blocks writes whose content
contains dangerous-code literals (dynamic code-execution calls, shell-exec
helpers, etc.). The `code-search` reference docs are *about searching for* such
patterns — keep examples benign (`logger.debug(...)`, `requests.get(...)`); if a
write is blocked, reword the example rather than disabling hooks.
