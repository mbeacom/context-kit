# context-kit

A context-engineering plugin pack for **GitHub Copilot CLI**, Microsoft's
[APM](https://github.com/microsoft/apm) (Agent Package Manager), and
[Claude Code](https://code.claude.com) — getting the right information in front of
an agent and keeping the wrong information out. It bundles complementary
**retrieval modalities** — lexical, structural, code-intelligence,
structured-data, history, semantic (RAG), graph, and durable memory — plus a
routing agent that picks and composes them. Default workflows keep indexes and
reviewed records on your machine. Configured model endpoints, providers, and
allowlisted commands can still reach external systems. Around that spine it adds
**plan-execute** (a strong model plans; cheaper subagents execute),
**context-steering** (put each rule at the cheapest layer that still fires),
**verify** (read-only claims and change-impact analysis), **runtime-evidence**
(controlled escalation when static checks cannot settle a runtime claim),
**corpus-review** (exhaustive review with a provable coverage ledger),
**deep-review** (multi-lens critique whose findings are typed and whose
disagreements survive),
**context-handoff** (bounded cross-session task state), **memory**
(provenance-bound durable recall with an optional MemPalace provider),
**token-economics** (measure token spend and prove tool savings), and
**plugin-forge** (author and quality-check portable plugins). The marketplace
ships fourteen plugins.

📖 **[Documentation site](https://mbeacom.github.io/context-kit/)** — install
guides, architecture, and a page for every plugin.

Start with the task-oriented [cookbook](docs/cookbook.md), review
[security and trust boundaries](docs/security.md), or diagnose first-run and
lifecycle problems in [troubleshooting](docs/troubleshooting.md). Vulnerability
reports follow the root [security policy](SECURITY.md).

All three hosts install the same plugins directly from one marketplace — GitHub
Copilot CLI via `copilot plugin`, APM via `apm install`, and Claude Code via
`/plugin` — no manual copying of skill folders. The catalog ships in Claude Code's
marketplace schema, which Copilot and APM read too.

## GitHub Copilot install

GitHub Copilot CLI installs these plugins directly from the marketplace — the same
`OWNER/REPO` this repo publishes:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install code-search@context-kit      # auto-installs retrieval-core
copilot plugin install local-rag@context-kit
copilot plugin install obsidian@context-kit
copilot plugin install plan-execute@context-kit   # plan-big/execute-small orchestration
copilot plugin install context-steering@context-kit
copilot plugin install verify@context-kit          # auto-installs retrieval-core
copilot plugin install runtime-evidence@context-kit # pulls verify, then retrieval-core
copilot plugin install corpus-review@context-kit    # pulls plan-execute + verify
copilot plugin install deep-review@context-kit      # pulls plan-execute + verify
copilot plugin install context-handoff@context-kit  # pulls verify, then retrieval-core
copilot plugin install memory@context-kit           # pulls handoff, verify, retrieval-core
copilot plugin install plugin-forge@context-kit
```

See [docs/GITHUB_COPILOT.md](docs/GITHUB_COPILOT.md) for details, including the
`local-rag` CLI bootstrap (Copilot CLI runs the plugin's `SessionStart` hook,
but a stale venv can still need an explicit rebuild).

## APM (Agent Package Manager) install

[APM](https://github.com/microsoft/apm) installs the same plugins from the same
marketplace, adding a committed lockfile, audit/policy checks, transitive
dependency resolution, and cross-harness deploy. Register the marketplace, then
install:

```bash
apm marketplace add mbeacom/context-kit
apm install code-search@context-kit      # also pulls retrieval-core (the spine)
apm install local-rag@context-kit
apm install obsidian@context-kit
apm install plan-execute@context-kit
apm install context-steering@context-kit
apm install verify@context-kit           # also pulls retrieval-core
apm install runtime-evidence@context-kit # pulls verify, then retrieval-core
apm install corpus-review@context-kit    # pulls plan-execute + verify
apm install deep-review@context-kit      # pulls plan-execute + verify
apm install context-handoff@context-kit  # pulls verify, then retrieval-core
apm install memory@context-kit           # pulls handoff, verify, retrieval-core
apm install plugin-forge@context-kit
```

APM reads the repo's `.claude-plugin/marketplace.json` and each plugin's native
layout directly; each per-plugin `apm.yml` carries APM metadata and dependencies.
`runtime-evidence` and `context-handoff` depend on `verify`, which transitively
pulls `retrieval-core`; `memory` depends on `context-handoff`. See
[docs/APM.md](docs/APM.md) for
targets, the `local-rag` bootstrap (APM does not run Claude's `SessionStart` hook),
and maintainer notes.

## Claude Code install

```bash
/plugin marketplace add mbeacom/context-kit
```

Then install what you need (installing `code-search` auto-installs `retrieval-core`):

```bash
/plugin install code-search@context-kit     # lexical/structural/data/history search
/plugin install local-rag@context-kit        # local semantic search (turbovec + ollama)
/plugin install obsidian@context-kit          # Obsidian vault → RAG bridge
/plugin install plan-execute@context-kit      # plan-big/execute-small orchestration
/plugin install context-steering@context-kit  # place guidance at the cheapest layer
/plugin install verify@context-kit            # claims + change impact (pulls retrieval-core)
/plugin install runtime-evidence@context-kit  # controlled runtime evidence (pulls verify)
/plugin install corpus-review@context-kit     # exhaustive review with a coverage ledger
/plugin install deep-review@context-kit       # multi-lens critique (pulls plan-execute + verify)
/plugin install context-handoff@context-kit   # manual cross-session handoffs (pulls verify)
/plugin install memory@context-kit            # durable memory + optional MemPalace provider
/plugin install token-economics@context-kit   # measure token spend + prove tool savings
/plugin install plugin-forge@context-kit      # author portable plugins
```

## Plugins

| Plugin | What it does |
| --- | --- |
| **retrieval-core** | The spine: a `retrieval-strategist` agent + `retrieval-strategy` skill that choose and compose modalities. Other plugins depend on it. |
| **code-search** | Lexical (`rg`/`fd`), structural (`ast-grep`/`semgrep`), code-intelligence (LSP/`global`/`ctags`), structured-data (`jq`/`yq`/`gron`), history (`git` pickaxe/`difftastic`), structured rewrite (`comby`), metrics (`tokei`/`scc`), and non-code docs (`rga`/`pandoc`/`pdftotext`). Two skills: `code-search` (code) and `data-and-docs-search` (data/docs). |
| **local-rag** | Local-first semantic search: a `bin/rag` CLI that chunks a corpus, embeds it through a configurable **ollama** endpoint, and indexes it with **turbovec**. Adds opt-in FTS5/BM25 + vector reciprocal-rank fusion with `--hybrid`, incremental indexing, source offsets, and hybrid `--allowlist` scoping. |
| **obsidian** | A skill-only **RAG bridge**: turn an Obsidian vault's graph/tags (official `obsidian` CLI, or `rg` fallback) into a candidate set fed to `local-rag`. For authoring/Bases/Canvas, use [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills). |
| **plan-execute** | Plan-big/execute-small **orchestration**: a strong model plans and delegates token-heavy work to cheaper subagents. Ships a strategy skill (`CLAUDE_CODE_SUBAGENT_MODEL` + delegation prompt, and how `/advisor` differs), a `/plan-big-execute-small` command, a bundled Workflow, and an `execution-worker` subagent. |
| **context-steering** | **Steering**: a `context-budget` skill for choosing where each piece of guidance lives — always-on memory (`CLAUDE.md`/`AGENTS.md`), path-scoped rules, on-demand skills, subagents, MCP servers, or deterministic hooks — plus inert, copy-paste rule and hook examples. Keeps the always-on context budget small. |
| **verify** | **Verification and impact**: a read-only `verifier`, `verify-before-trust`, and prospective `change-impact` skill plus `/analyze-impact`. Checks claims and maps blast radius without editing or executing. Ships an enforced read-only inspection runner — a POSIX Python 3 stdlib executor with a fixed, plugin-owned catalog of non-mutating `git`/`jq`/`yq` operations, no shell, validated positional parameters, and a scrubbed environment — so history, structural, and structured-data evidence comes with a real guarantee or an explicit `unavailable`, never a silent downgrade. Composes with `retrieval-core`; `plan-execute` is optional for broad read-only coverage, not a dependency. |
| **runtime-evidence** | **Controlled observation**: escalates only runtime claims left `unable-to-check` by static verification. A POSIX-only Python 3 stdlib runner executes exact argv from a user-owned exact-ID JSON allowlist without shell parsing, requires an absolute cwd, caps time and each output stream, and writes report/stdout/stderr artifacts. Windows is refused before execution. When no reviewed command can represent the claim, an approved optional-tool observation (browser, debugger, container) runs in the main agent instead — bounded by the user's approval and the host, not by the plugin. Allowlisting constrains selection; it does not prove an executable has no side effects. |
| **corpus-review** | **Exhaustive review**: reads a corpus too large for one context and proves what was inspected. Standard-library scripts enumerate units with content hashes and an inspectability signal, pack them into bounded resumable shards that preserve original locations, and aggregate per-shard findings into a coverage ledger. Every unit ends as `reviewed`, `partial`, `uninspectable`, `out_of_scope`, `failed`, or `pending`, and aggregation exits nonzero while any unit is unaccounted for. An expected item nobody found is `not-found` only when everything that could contain it was actually read — a partial, uninspectable, failed, or pending unit makes it `indeterminate` instead. |
| **deep-review** | **Multi-lens judgment**: asks whether a work product is good and what will go wrong, which is neither a truth question nor a coverage question. Independent charters (`adversarial`, `architect`, `consumer`, `operator`, plus domain lenses) drive one parameterized worker, and each charter's stated non-scope is what stops four lenses from filing the same complaint. Findings are typed: a `DEFECT` must carry a concrete falsification and is routed to `verify` rather than graded here, a `RISK` must name its trigger, and a `JUDGMENT` is a preference the author may decline. A stdlib adjudicator merges corroborating findings into one entry keeping the highest severity asserted, surfaces conflicting resolutions at one location as unresolved tradeoffs instead of picking a winner, and exits nonzero when a declared lens produced no report — a crashed lens is reported, never read as clean. |
| **context-handoff** | **Session continuity**: manual-first `/write-handoff` and `/resume-handoff`, a read-only compiler, and a deterministic Python 3 validator for bounded task state. Defaults to `.context-kit/handoff.md` or `CONTEXT_KIT_HANDOFF_PATH`; detects invalid, mismatched, and stale state. It has no lifecycle hooks or automatic RAG/memory ingestion. |
| **memory** | **Durable recall**: reviewed `context-kit/memory-v1` records with immutable evidence, primary memories, cue anchors, freshness, and supersession. Ships capture/recall/review/archive commands, a stdlib adapter for optional MemPalace, project-isolated storage, and opt-in Claude capture hooks. |
| **token-economics** | **Measurement**: reports what an agent actually spent, and settles whether a tool caused a saving. A stdlib reader deduplicates Claude Code's replayed responses on `(requestId, message.id)` and decomposes cache traffic per host — Copilot's `input_tokens` includes cache while Claude Code's excludes it, so the naive reading is wrong in opposite directions. Cost is reported only in the unit a host recorded: Copilot rows carry their own per-model rate card, and Claude Code records none. Savings claims go through a controlled A/B that requires a preserved-answer assertion, because discarding output "saves" 100%; a run without one is `unverified` and not quotable. Every figure carries a counting grade and an attribution grade — telemetry is always observational and can never attribute a change to a tool. |
| **plugin-forge** | **Authoring quality**: portable-plugin conventions, `/scaffold-plugin`, manifest and discovery checks, a 4096-character aggregate discovery budget with a 95% warning band and a 384-character per-component ceiling, overlap/fixture/agent-contract checks, regression tests, and a mocked no-network workflow smoke test. Static fixtures check catalog hygiene, not model routing. |

## Requirements

The skills degrade gracefully and tell you what's missing.

- **code-search** — needs `rg` (ripgrep); the rest are optional. Run
  `bash plugins/code-search/scripts/check-tools.sh` to see what's installed and
  the `brew install …` line for the rest.
- **local-rag** — needs [`uv`](https://docs.astral.sh/uv/) and a running
  [ollama](https://ollama.com) with an embedding model. For GitHub Copilot, APM,
  or manual use, run the bootstrap step in
  [docs/GITHUB_COPILOT.md](docs/GITHUB_COPILOT.md) (`ollama serve` +
  `ollama pull nomic-embed-text`); Claude Code auto-bootstraps the `rag` CLI on
  session start.
- **obsidian** — optional: the official `obsidian` CLI (with Obsidian running)
  for graph-accurate queries; otherwise falls back to `rg`/`fd`. Set your vault
  path via `CONTEXT_KIT_OBSIDIAN_VAULT` (GitHub Copilot, APM, or manual usage) or
  the Claude plugin config (`vault_path`).
- **corpus-review** — needs Python 3 for its standard-library inventory, shard,
  and aggregation scripts. Extracting non-text units (PDF, Office, archives)
  relies on the optional `data-and-docs-search` tools above.
- **deep-review** — needs Python 3 for its standard-library adjudicator. No
  other tooling; the lenses are subagents, not external tools.
- **runtime-evidence** and **context-handoff** — need Python 3 for their
  standard-library runner and deterministic validator. The runtime runner
  requires POSIX and refuses Windows before execution; the handoff validator is
  cross-platform. Runtime evidence's optional-tool path ships no runner, so it
  needs neither Python nor POSIX — only an approved, host-exposed observation
  tool.
- **memory** — needs Python 3 for local reviewed records. Provider-backed recall
  optionally uses a separately installed `mempalace` CLI (`uv tool install
  mempalace`); automatic capture is disabled by default.

## Usage

Once installed in GitHub Copilot, APM, or Claude Code, your agent can load
the skills automatically based on your task. The **`retrieval-strategist`** agent
(or the `retrieval-strategy` skill) decides which modality fits — and they
**compose**.

**Pick a modality by what you know:**

| You know… | Modality | Example |
| --- | --- | --- |
| an exact token / regex / filename | lexical | `rg -t py 'def login'` · `fd -e ts` |
| the code *shape*, not the text | structural | `sg -p 'logger.debug($$$)' --lang js` |
| the *symbol* — its defs / refs / callers | code-intelligence | `global -xr parseConfig` · `ctags -R` |
| a JSON/YAML schema path | structured-data | `jq '.scripts' package.json` · `gron x.json \| rg token` |
| *when/why* code changed | history | `git log -S'retry' -- src/` |
| only the *meaning/intent* | semantic (RAG) | `rag query "how do we handle backoff" --name notes` |
| the corpus is an Obsidian vault | graph | `obsidian backlinks file="Project X"` |
| a prior decision, constraint, or episode | durable memory | `/recall-memory "why did we change retries?"` |

**Semantic search (local-rag):**

```bash
ollama pull nomic-embed-text                 # once
rag index /path/to/vault --name notes        # build/update (incremental)
rag query "open questions about billing" --name notes --k 8
rag query "open questions about billing" --name notes --k 8 --hybrid
rag status --name notes                       # counts, model, dim
rag list                                      # known indexes
rag remove --name notes --yes                 # permanent; --yes is required
```

**Hybrid retrieval (the payoff) — narrow with the graph/lexical, rerank with vectors:**

```bash
# Obsidian graph → semantic rerank (official CLI)
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -

# rg fallback when Obsidian isn't running ($VAULT defaults to the plugin's configured vault_path)
VAULT="${CONTEXT_KIT_OBSIDIAN_VAULT:-${CLAUDE_PLUGIN_OPTION_VAULT_PATH:-.}}"
rg -l '#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

`--hybrid` fuses vector and SQLite FTS5/BM25 candidates with deterministic
reciprocal-rank fusion. `rag` returns `path > heading` plus a snippet; JSON also
includes source offsets and signal ranks/scores. Follow up with `rg` or Read to
pin exact evidence.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the modality model and how the
plugins fit together.

## Development

```bash
# Validate the marketplace + every plugin
claude plugin validate . --strict
for p in plugins/*/; do claude plugin validate "$p" --strict; done

# Lint (markdownlint + shellcheck + ruff + hygiene)
pre-commit run --all-files

# Run catalog gates and focused unit tests
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
python3 -m unittest discover -s plugins/runtime-evidence/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/verify/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/context-handoff/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/memory/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/corpus-review/tests -p 'test_*.py'
python3 -m unittest discover -s plugins/deep-review/tests -p 'test_*.py'
python3 -m unittest discover -s tests/integration -p 'test_*.py'

# Run the local-rag Python tests
cd plugins/local-rag && uv run --group dev pytest -q
```

See [CLAUDE.md](CLAUDE.md) and
[.github/copilot-instructions.md](.github/copilot-instructions.md) for
contributor conventions.

## License

MIT © Mark Beacom. Each plugin ships its own `LICENSE`.
