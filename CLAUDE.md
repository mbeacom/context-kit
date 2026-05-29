# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`productivity-skills` is a **Claude Code plugin marketplace** and a
**GitHub Copilot-compatible Agent Skills pack** (not an application). It is a
catalog of plugins/skills organized around **retrieval modalities** —
complementary ways an agent finds information (lexical, structural,
structured-data, history, semantic/RAG, graph), selected by what's known about
the query and corpus, and composed together. See `docs/ARCHITECTURE.md` for the
modality model and `docs/GITHUB_COPILOT.md` for Copilot setup notes.

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
  `src/local_rag/`, run via a uv venv bootstrapped into `${CLAUDE_PLUGIN_DATA}`
  by a Claude `SessionStart` hook, or `${PRODUCTIVITY_SKILLS_DATA}` for
  Copilot/manual usage) that chunks → embeds via `ollama` → indexes with
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
- **GitHub Copilot compatibility:** keep reusable workflow knowledge in
  `SKILL.md` + `references/` so it can be copied to `.github/skills/` or
  `~/.copilot/skills/`; prefer portable `PRODUCTIVITY_SKILLS_*` env examples
  with `CLAUDE_PLUGIN_*` documented as Claude fallbacks.
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

<!-- rtk-instructions v2 -->
## RTK (Rust Token Killer) - Token-Optimized Commands

### Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:

```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

### RTK Commands by Workflow

#### Build & Compile (80-90% savings)

```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

#### Test (60-99% savings)

```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

#### Git (59-80% savings)

```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

#### GitHub (26-87% savings)

```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

#### JavaScript/TypeScript Tooling (70-90% savings)

```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

#### Files & Search (60-75% savings)

```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

#### Analysis & Debug (70-90% savings)

```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

#### Infrastructure (85% savings)

```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

#### Network (65-70% savings)

```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

#### Meta Commands

```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

### Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->

> **rtk + pipes:** the "always prefix" rule above is safe for output you read,
> but rtk *reformats* wrapped-command output, which can corrupt data piped into
> another program. Use raw-preserving flags (`-c`/`-l`) or `rtk proxy <cmd>` for
> intermediate pipe stages. See
> `plugins/code-search/skills/code-search/references/rtk.md`.
