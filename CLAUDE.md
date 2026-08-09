# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Shared, host-neutral rules live in [`AGENTS.md`](AGENTS.md); this file adds Claude-specific detail (hooks, `${CLAUDE_PLUGIN_*}`, RTK) on top of them.

## What this repo is

`context-kit` is a **Claude Code plugin marketplace** and a
**GitHub Copilot-compatible Agent Skills pack** (not an application). It is a
catalog of plugins/skills for **context engineering** — getting the right
information in front of an agent and keeping the wrong information out. Its spine
is organized around **retrieval modalities** — complementary ways an agent finds
information (lexical, structural, code-intelligence, structured-data, history, semantic/RAG, graph),
selected by what's known about the query and corpus, and composed together —
surrounded by plugins for durable memory, orchestration, steering, verification,
controlled runtime evidence, cross-session handoff, and authoring.
See `docs/ARCHITECTURE.md` for the modality model and `docs/GITHUB_COPILOT.md` for
Copilot setup notes.

## Layout

- `.claude-plugin/marketplace.json` — the catalog. **Lists only shipped plugins.**
  Hand-authored (read by Claude Code, Copilot, and APM alike); **not** generated —
  see the APM convention below.
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/apm.yml` — per-plugin [APM](https://github.com/microsoft/apm)
  (Agent Package Manager) manifest, mirroring `plugin.json`. No `.apm/` dir, so the
  plugin-native layout stays authoritative; APM consumes it as a plugin collection.
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
- `indexkit` — local-first semantic RAG. A `bin/indexkit` CLI (Python package under
  `src/indexkit/`, run via a uv venv bootstrapped into `${CLAUDE_PLUGIN_DATA}`
  by a Claude `SessionStart` hook, or `${CONTEXT_KIT_DATA}` for
  Copilot/manual usage) that chunks → embeds via `ollama` → indexes with
  `turbovec`. All turbovec usage is isolated to `src/indexkit/index.py`.
- `obsidian` — a **skill-only** RAG bridge (no code/deps): vault graph/tags
  (official `obsidian` CLI, or `rg` fallback) → `indexkit query --allowlist`. Authoring
  / Bases / Canvas are out of scope (defer to `kepano/obsidian-skills`).
- `plan-execute` — plan-big/execute-small **orchestration**: a strong planner
  delegates token-heavy work to a cheap `execution-worker` subagent. Ships a
  strategy skill, a `/plan-big-execute-small` command, and a bundled Workflow.
- `context-steering` — a **skill-only** teaching plugin: the `context-budget`
  skill (a decision matrix for placing guidance in memory vs path-scoped rules vs
  skills vs subagents vs hooks) plus inert `examples/` (rules + hooks). Ships NO
  active hooks/rules — the examples are copy-paste templates.
- `verify` — a read-only `verifier` subagent (tools: Read/Grep/Glob only) + a
  `verify-before-trust` skill for claim verdicts and a prospective, read-only
  `change-impact` skill + `/analyze-impact` command for blast-radius analysis.
  Ships `scripts/run-impact-inspection.py`, a POSIX stdlib runner with a fixed,
  plugin-owned catalog of non-mutating `git`/`jq`/`yq` operations (no shell,
  validated positional parameters, path confinement, scrubbed environment) so
  history, structural, and structured-data modalities are enforced rather than
  merely instructed; a missing tool exits `unavailable` instead of downgrading.
  Declares
  `dependencies: ["retrieval-core"]`.
- `runtime-evidence` — static-verification escalation for runtime claims. Its
  stdlib Python runner executes exact argv selected by exact command ID from a
  user-owned JSON allowlist, without a shell, and writes bounded artifacts.
  Declares `dependencies: ["verify"]`.
- `corpus-review` — exhaustive review of a corpus too large to read in one
  context, as a capability distinct from retrieval. Standard-library scripts
  enumerate hashed units with an inspectability signal, pack them into bounded
  resumable shards that preserve original locations, and aggregate per-shard
  findings into a coverage ledger. Every unit ends `reviewed`, `partial`,
  `uninspectable`, `out_of_scope`, `failed`, or `pending`; `indeterminate`
  outranks `not-found`, so a partially read, uninspectable, failed, or pending
  unit is never treated as evidence of absence.
  Declares `dependencies: ["plan-execute", "verify"]`.
- `deep-review` — multi-lens evaluative review, as a capability distinct from
  claim verification and coverage: it asks whether a work product is good and
  what will go wrong. Independent charters (`adversarial`, `architect`,
  `consumer`, `operator`, plus caller-defined domain lenses) drive one
  parameterized `review-lens` worker rather than one agent per persona.
  Findings are typed — `DEFECT` (routed to `verify`), `RISK` (needs a stated
  trigger), `JUDGMENT`, `QUESTION` — and a stdlib adjudicator merges
  corroborating findings into one entry, surfaces conflicting resolutions as
  unresolved tradeoffs rather than resolving them, and exits nonzero when a
  declared lens produced no report.
  Declares `dependencies: ["plan-execute", "verify"]`.
- `context-handoff` — manual-first `/write-handoff` and `/resume-handoff`
  workflow with a read-only compiler and deterministic validator. It has no
  lifecycle hooks or automatic RAG/memory ingestion; explicit historical
  archival belongs to `memory`. Declares
  `dependencies: ["verify"]`.
- `memory` — reviewed `context-kit/memory-v1` records (immutable evidence,
  primary memory, cue anchors, freshness, supersession), capture/recall/review/
  archive commands, and a stdlib adapter for an optional separately installed
  MemPalace CLI. Provider storage is project-isolated; Claude lifecycle hooks are
  inert unless explicitly enabled. Declares `dependencies: ["context-handoff"]`.
- `token-economics` — measurement, as a capability distinct from retrieval and
  verification: what an agent actually spent, and whether a tool caused a saving.
  A stdlib reader deduplicates Claude Code's replayed responses on
  `(requestId, message.id)` and decomposes cache traffic per host, since
  Copilot's `input_tokens` includes cache while Claude Code's excludes it. Cost
  is reported only in the unit a host recorded. Savings claims run through a
  controlled A/B requiring a preserved-answer assertion — discarding output
  "saves" 100% — and a run without one is `unverified` rather than quotable.
  Every figure carries a counting grade and an attribution grade; telemetry is
  always observational. Declares `dependencies: ["verify"]`.
- `plugin-forge` — authoring toolkit for portable plugins: the
  `authoring-portable-plugins` skill, `/scaffold-plugin`, manifest/frontmatter
  validators, and a deterministic aggregate catalog-quality gate with regression
  tests and a mocked no-network workflow smoke test.

## Commands

- Validate one plugin: `claude plugin validate ./plugins/<name> --strict`
- Validate all plugins:
  `for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done`
- Lint everything (markdownlint + shellcheck + hygiene + manifest/skill checks): `pre-commit run --all-files`
- Check manifest sync, skill discovery frontmatter, and command frontmatter directly:
  `bash plugins/plugin-forge/scripts/check-manifests.sh` · `bash plugins/plugin-forge/scripts/check-skills.sh` ·
  `bash plugins/plugin-forge/scripts/check-commands.sh`
- Check and test aggregate catalog quality:
  `bash plugins/plugin-forge/scripts/check-catalog-quality.sh` ·
  `bash plugins/plugin-forge/scripts/test-catalog-quality.sh`
- Preview the CI-only version-bump gate against your PR base:
  `bash plugins/plugin-forge/scripts/check-version-bump.sh --base main`
- Smoke-test the APM path (needs the `apm` CLI): from a clone,
  `apm marketplace add ./ --name ps` then, in a scratch dir,
  `apm install code-search@ps --target claude` — verify it deploys both
  `code-search` and the `retrieval-core` spine, then `apm marketplace remove ps`.
- Report which search CLIs are installed: `bash plugins/code-search/scripts/check-tools.sh`
  (a non-zero exit listing `brew install …` for missing optional tools is expected, not a failure).
- Run the `indexkit` Python tests: `cd plugins/indexkit && uv run --group dev pytest -q`
  (uv resolves a dev venv; no live ollama needed — the embed client is mocked, turbovec is exercised for real).
- Run the stdlib plugin tests:
  `python3 -m unittest discover -s plugins/runtime-evidence/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/verify/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/context-handoff/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/memory/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/corpus-review/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/deep-review/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/token-economics/tests -p 'test_*.py'` ·
  `python3 -m unittest discover -s plugins/plugin-forge/tests -p 'test_command_frontmatter.py'` ·
  `python3 -m unittest discover -s tests/release -p 'test_*.py'` ·
  `python3 -m unittest discover -s tests/integration -p 'test_*.py'`
- Rebuild the `indexkit` runtime venv manually: `bash plugins/indexkit/scripts/bootstrap.sh`
  (normally automatic on `SessionStart`; it reinstalls only when `pyproject.toml` changes).

CI (`.github/workflows/validate.yml`) runs `claude plugin validate --strict` on
every plugin, `pre-commit` (including catalog gates), the pull-request-only
version-bump gate, and the `indexkit` pytest suite plus the runtime-evidence,
context-handoff, memory, corpus-review, deep-review, and cross-plugin
standard-library
suites.

## Conventions when modifying this repo

- **Adding a plugin:** create `plugins/<name>/.claude-plugin/plugin.json` (include
  `$schema`, `name`, `displayName`, `version`, `description`, `author`,
  `homepage`/`repository`, `license`, `keywords`), add `skills/`/`agents/`, add a
  `plugins/<name>/apm.yml` (see the APM convention below), add a
  `LICENSE` + `CHANGELOG.md`. Add a catalog entry to `marketplace.json` **only
  when the plugin is ready** — stubs stay unlisted so they can't be installed
  half-built.
- **Versioning:** bump `version` in `plugin.json` to ship updates — Claude Code
  uses it as the cache key, so pushing commits without a bump ships nothing. Bump
  the matching `apm.yml` `version` in lockstep. CI enforces this on pull requests
  via `check-version-bump.sh`: shipped content changed across `merge-base..HEAD`
  must carry a strictly-greater version. Docs-only, test-only, and `CHANGELOG.md`
  edits are exempt; skip deliberately with a
  `Skip-Version-Bump: <plugin> - <reason>` commit trailer, which the gate echoes
  into the CI log.
- **APM (Agent Package Manager) compatibility:** each plugin ships an `apm.yml`
  that mirrors its `plugin.json` (`name`/`version` kept strictly in sync;
  `description` is intentionally a more concise variant tuned for APM/CLI
  listings). Do
  **not** add an `.apm/` directory — its absence keeps the plugin-native layout
  authoritative. APM does not read the plugin.json `dependencies` field, so
  inter-plugin dependencies live in `apm.yml` (e.g. `code-search` → a local-path
  dep on `../retrieval-core`). Keep `marketplace.json` **hand-authored**: do not
  run `apm pack` to regenerate it — the generated output drops the per-plugin
  `category` field. (That drop is fixed upstream by microsoft/apm#2189, merged but
  unreleased as of 2026-07; even after it ships, re-verify `apm pack` output before
  relaxing this.) See [docs/APM.md](docs/APM.md).
- **GitHub Copilot compatibility:** GitHub Copilot CLI installs these plugins
  directly (`copilot plugin marketplace add` + `copilot plugin install`), so keep
  reusable workflow knowledge in `SKILL.md` + `references/` and portable across
  hosts; prefer `CONTEXT_KIT_*` env examples with `CLAUDE_PLUGIN_*`
  documented as Claude fallbacks.
- **Licensing:** repo and all plugins are MIT (Mark Beacom). Each plugin ships
  its own `LICENSE`. Content is written fresh; do not copy text from externally
  licensed sources (e.g. the CC-BY-SA upstream that inspired `code-search`).
- **Skill granularity:** prefer few well-scoped skills with `references/` for
  detail over many fine-grained skills (always-on token cost scales with skill
  count). `code-search` uses two skills split by corpus (code vs data/docs). The
  cost is capped by a fixed 4096-character aggregate discovery budget plus a
  384-character per-component ceiling; `check-catalog-quality.sh` warns at 95%
  and fails above the limit. See `AGENTS.md` and
  `plugins/plugin-forge/skills/authoring-portable-plugins/references/catalog-quality.md`.
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
