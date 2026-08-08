# Contributing

`context-kit` is a Claude Code **plugin marketplace** and a Copilot/APM-compatible
Agent Skills pack — a catalog of plugins, not an application. The reusable value
lives in `SKILL.md` files, their `references/`, subagents, and local CLI
workflows.

## Repository layout

| Path | Purpose |
| --- | --- |
| `.claude-plugin/marketplace.json` | The catalog (hand-authored; lists shipped plugins only). |
| `plugins/<name>/.claude-plugin/plugin.json` | Per-plugin manifest (Claude Code + Copilot). |
| `plugins/<name>/apm.yml` | Per-plugin APM manifest, mirroring `plugin.json`. |
| `plugins/<name>/skills/<name>/SKILL.md` | Skills, with `references/*.md` for detail. |
| `plugins/<name>/agents/<name>.md` | Subagents. |
| `docs/` | This documentation site (MkDocs Material). |

Component directories (`skills/`, `agents/`, `scripts/`) live at the **plugin
root**, never inside `.claude-plugin/` (that dir holds only `plugin.json`).

## Validate, lint, and test

```bash
# Validate the marketplace + every plugin
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done

# Lint everything (markdownlint + shellcheck + ruff + hygiene)
pre-commit run --all-files

# Run the aggregate catalog gate and its regression/smoke tests
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh

# Run the focused standard-library suites and their cross-plugin integration
python3 -m unittest discover -s plugins/runtime-evidence/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/verify/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/context-handoff/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/memory/tests -p 'test_*.py'
python3 -m unittest discover -s tests/integration -p 'test_*.py'

# Lint the ADR corpus (skips cleanly if Node is unavailable)
bash scripts/check-adr.sh

# Run the indexkit Python tests
cd plugins/indexkit && uv run --group dev pytest -q
```

CI (`.github/workflows/validate.yml`) runs `claude plugin validate --strict` on
every plugin, `pre-commit` (including release-readiness and catalog-quality
checks), and the `indexkit` pytest suite plus all focused standard-library
suites above.
The integration suite uses a temporary local Git repository, the real script
entry points, local memory mode, and no network or external MemPalace process.

## Build the docs locally

The site is [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). Serve
it with live reload, or build a static copy:

```bash
# Live preview at http://127.0.0.1:8000
uv run --with-requirements docs/requirements.txt mkdocs serve

# Production build (strict: fail on broken links / nav)
uv run --with-requirements docs/requirements.txt mkdocs build --strict
```

The `main` branch deploys to GitHub Pages automatically via
`.github/workflows/docs.yml`. The build output (`/site`) is git-ignored.

## Conventions

- **Adding a plugin** — create `plugins/<name>/.claude-plugin/plugin.json`, add
  `skills/`/`agents/`, add a sibling `apm.yml`, and a `LICENSE` + `CHANGELOG.md`.
  Add the `marketplace.json` catalog entry **only when the plugin is ready** —
  stubs stay unlisted so they can't be installed half-built. Add a page here under
  `docs/plugins/` and wire it into `mkdocs.yml`. Add central positive/negative
  discovery fixtures and keep the aggregate description budget within 4096
  characters (384 per component). The catalog gate warns at 95% of the budget.
- **Versioning** — bump `version` in `plugin.json` to ship updates (Claude Code
  uses it as the cache key). Bump the matching `apm.yml` `version` in lockstep;
  `plugin-forge`'s `check-manifests.sh` enforces this. Add the same version as the
  top release in that plugin's `CHANGELOG.md`; the release-readiness gate enforces
  the changelog and dependency graph invariants. On pull requests, CI also runs
  `check-version-bump.sh`, which fails when shipped plugin content changed without
  a strictly-greater version. Docs-only, test-only, and `CHANGELOG.md` edits are
  exempt; to skip deliberately, add a `Skip-Version-Bump: <plugin> - <reason>`
  trailer to a commit so the exemption is visible in review and in the CI log.
- **Portability** — keep skill bodies host-neutral. Prefer `CONTEXT_KIT_*`
  environment variables in examples, with `CLAUDE_PLUGIN_*` documented as the
  Claude fallback. Keep marketplace mechanics in `.claude-plugin/` and Claude-only
  docs.
- **Architecture decisions** — decisions that are hard to reverse, contested, or
  govern a path are recorded as ADRs in [`docs/adr/`](https://github.com/mbeacom/context-kit/tree/main/docs/adr),
  managed by [adrkit](https://github.com/mbeacom/adrkit) ([ADR-0001](https://github.com/mbeacom/context-kit/blob/main/docs/adr/0001-record-architecture-decisions-with-adrkit.md)).
  The instruction files keep the *rules*; the corpus keeps the *reasoning, the
  rejected options, and the revisit conditions*. Create one with
  `npx @adrkit/cli@0.4.0 new "<title>"`, fill in `affects` so the decision is
  locatable by path, and check what already governs a file with
  `npx @adrkit/cli@0.4.0 explain <path>`. Do **not** write an ADR for naming,
  formatting, or anything a contributor can flip in one commit.
  Code that exists *because of* a decision — compatibility shims especially —
  can declare it inline with a dedicated `# @adr NNNN` comment line, which
  `adr explain` reports as `declared by <file>:<line>`. Markers must be real
  comment lines (not docstrings) within the first 8192 bytes of the file, so in
  a large module put them in the header.
  adrkit is contributor-side only — no shipped plugin depends on it, and
  `scripts/check-adr.sh` skips cleanly when Node is absent, so you can work
  without it. An agent-drafted record cannot reach `accepted` without a named
  human ratifier in `provenance.ratifiedBy`; that refusal is intentional.
- **Licensing** — repo and all plugins are MIT (Mark Beacom). Content is written
  fresh; do not copy text from externally licensed sources. adrkit is Apache-2.0,
  so we invoke it as an external CLI and never vendor its code.
- **Markdown** — `.markdownlint-cli2.jsonc` disables MD013/MD033/MD041/MD060. Fix
  real lint findings rather than disabling more rules. `docs/adr/` extends that
  config with one scoped option so MD025 tolerates adrkit's frontmatter title
  alongside its H1.

See [`CLAUDE.md`](https://github.com/mbeacom/context-kit/blob/main/CLAUDE.md) and
[`.github/copilot-instructions.md`](https://github.com/mbeacom/context-kit/blob/main/.github/copilot-instructions.md)
for the full contributor guide.

See [Releasing plugins](releasing.md) for the maintainer release, tag, and
recovery procedure.
