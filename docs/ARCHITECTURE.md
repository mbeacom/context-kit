# Architecture

`context-kit` is a context-engineering plugin pack for **GitHub Copilot CLI**,
**APM** (Agent Package Manager), and **Claude Code**. Its
spine is organized around **retrieval modalities** — complementary ways an agent
finds information, selected by what it knows about the query and the corpus, and
composed together — surrounded by durable recall (`memory`), orchestration
(`plan-execute`), steering (`context-steering`), verification and impact
analysis (`verify`), controlled runtime observation (`runtime-evidence`),
cross-session continuity (`context-handoff`), and authoring quality
(`plugin-forge`).

All three hosts install the same plugins directly from one marketplace — GitHub
Copilot CLI via `copilot plugin`, APM via `apm install`, and Claude Code via
`/plugin`. The catalog ships in Claude Code's marketplace schema, which Copilot and
APM read too. The retrieval instructions in each `SKILL.md` are identical across
hosts.

## Modalities

| Modality        | Tools                              | Use when you know…                          |
| --------------- | ---------------------------------- | ------------------------------------------- |
| Lexical         | `rg`, `fd`                         | the exact token / regex / filename          |
| Structural      | `ast-grep`, `semgrep`              | the code *shape*, not the literal text      |
| Code-intel.     | LSP, `global`, `ctags`             | the *symbol* — its defs / refs / callers    |
| Structured-data | `jq`, `yq`, `gron`                 | the *schema* (JSON / YAML / config)         |
| History         | `git log -S/-G/-L`, `difftastic`   | *when / why* something changed              |
| Data files      | `duckdb`, `sqlite-utils`           | tabular corpora (CSV / Parquet / JSON)      |
| Metrics         | `tokei`, `scc`                     | size / complexity of a codebase             |
| Non-code docs   | `rga`, `pandoc`, `pdftotext`       | content in PDFs / Office docs / archives    |
| Semantic (RAG)  | `turbovec` + `ollama`              | only the meaning/intent; large/prose corpus |
| Graph           | Obsidian wikilinks / backlinks     | human-authored relationships                |
| Durable memory  | reviewed records + optional MemPalace | prior decisions, constraints, procedures, episodes |

Modalities **compose**: lexical/structured narrows → vectors rerank
(turbovec `allowlist`); `local-rag --hybrid` fuses vector and FTS5/BM25 ranks;
graph backlinks scope a subgraph → RAG within it; memory recalls prior context →
the source and current repository evidence pin the claim.

## Plugins

| Plugin           | Status   | Purpose                                                    |
| ---------------- | -------- | ---------------------------------------------------------- |
| `retrieval-core` | shipped  | Routing agent + decision-flow skill (the spine)            |
| `code-search`    | shipped  | Lexical/structural/code-intel/data/history/rewrite/metrics/doc search |
| `local-rag`      | shipped  | Local semantic/hybrid RAG: turbovec + ollama + optional FTS5/BM25 RRF |
| `obsidian`       | shipped  | Skill-only RAG bridge: vault graph/tags → `rag query --allowlist` |
| `plan-execute`   | shipped  | Plan-big/execute-small orchestration: planner + cheap `execution-worker` |
| `context-steering` | shipped | Skill-only: place guidance at the cheapest layer (memory/rules/skills/subagents/mcp/hooks) |
| `verify`         | shipped  | Read-only claim verdicts + prospective change-impact analysis |
| `runtime-evidence` | shipped | Exact-ID allowlisted runtime evidence after static verification cannot settle a claim |
| `context-handoff` | shipped | Manual bounded write/resume handoffs with provenance and freshness validation |
| `memory`         | shipped  | Reviewed durable records + optional project-isolated MemPalace provider |
| `plugin-forge`   | shipped  | Portable-plugin scaffold, validators, and deterministic catalog-quality gate |

`code-search` and `verify` declare `dependencies: ["retrieval-core"]`.
`runtime-evidence` and `context-handoff` depend on `verify`, so installing either
transitively pulls the retrieval spine. Runtime evidence does not replace static
retrieval: it is an explicit escalation only after verification remains
`unable-to-check`. Context handoffs carry bounded verified state between sessions;
they are not chat persistence or automatic RAG ingestion. `memory` depends on
`context-handoff`; it can preserve a validated handoff only as an explicit
historical archive. Its recall results never override current handoff or
repository evidence.
`local-rag` and `obsidian` pair: the obsidian bridge produces candidate note paths
that feed `local-rag`'s hybrid `--allowlist` search. Obsidian *authoring*
(Markdown, Bases, Canvas) is intentionally out of scope — use
[`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) and the
official `obsidian` CLI for that.

## Composition in practice

The modalities are layers, not rivals — `retrieval-core` sequences them:

- **Hybrid rerank** — lexical/structured-data or the obsidian graph narrows to a
  candidate file set → `rag query --allowlist -` reranks only those by meaning
  (turbovec's native allowlist).
- **Scope then search** — graph backlinks/tags bound a subgraph → RAG within it.
- **Find then pin** — RAG surfaces `path > heading` regions → `rg` pins exact lines.
- **Resolve then pin** — code-intelligence (LSP/`global`) returns the true symbol defs/refs → `rg` pins the exact lines.
- **Recall then pin** — durable memory finds a prior decision/episode → open its
  evidence and pin what is true in the current repository.
- **Recall then verify** — stale, conflicting, or consequential memory returns
  to `verify` before it drives behavior.
- **Retrieve then expand** — follow bounded cue, neighbor, or source links only
  when the compact result is insufficient.
- **Verify then observe** — repository evidence produces a verdict; only an
  unresolved runtime claim can escalate through `runtime-evidence`'s exact-ID
  allowlisted runner, and its bounded artifacts return to `verify`.
- **Verify then hand off** — `context-handoff` compiles bounded task state with
  repository provenance; resume rejects identity mismatches and reverifies stale
  claims before acting.

## Deterministic retrieval contracts

Plugin Forge validates the routing model above against
`plugins/plugin-forge/quality/retrieval-scenarios.json`. The schema-v1 corpus
declares route ownership and tools, named composition step variants, and stable
scenarios with query/corpus cues, expected primary routes, participating
plugins/tools, rationales, and near misses.

The blocking gate requires all 11 modalities, the handoff/verification/runtime
evidence non-retrieval routes, and all nine compositions to remain represented.
It rejects stale cross-plugin/tool references and composition-step drift. This is
contract and coverage validation only: no model runs in CI, and passing does not
measure routing accuracy. Future scheduled live-model evaluation can consume the
same stable corpus and store probabilistic trend results separately.

`local-rag` keeps everything local: ollama for embeddings, turbovec for the index,
and SQLite FTS5/BM25 for opt-in hybrid rank fusion
(persisted under `${CONTEXT_KIT_DATA}` or, in Claude Code,
`${CLAUDE_PLUGIN_DATA}`), nothing leaves the machine. The markdown loader is the
first-class path, but the indexer is built behind a pluggable loader interface so
other corpora (code, PDFs) can be added without a redesign.

## Agent host compatibility

| Host | What it uses | Notes |
| ---- | ------------ | ----- |
| GitHub Copilot | the marketplace, via `copilot plugin marketplace add` + `copilot plugin install` | Installs plugins (skills, agents, commands) directly; run the local CLIs yourself. |
| APM | the same marketplace + each plugin's `apm.yml`, via `apm marketplace add` + `apm install` | Cross-harness deploy with a lockfile and pre-install security scan; run the local CLIs yourself. |
| Claude Code | `.claude-plugin/marketplace.json`, per-plugin manifests, hooks, `CLAUDE_PLUGIN_*` env vars | Install/update via `/plugin` commands; auto-bootstraps the `local-rag` CLI. |

Portable examples should prefer `CONTEXT_KIT_*` environment variables,
with `CLAUDE_PLUGIN_*` documented as the Claude plugin fallback. See
[GITHUB_COPILOT.md](GITHUB_COPILOT.md) for a concrete Copilot setup and
[APM.md](APM.md) for the APM path.

## Layout

- `.claude-plugin/marketplace.json` — catalog (lists shipped plugins only).
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/skills/<name>/SKILL.md` — skills (with `references/` for detail).
- `plugins/<name>/agents/<name>.md` — subagents.
- `plugins/local-rag/` also ships `bin/rag` (CLI), `src/local_rag/` (Python
  package), `scripts/bootstrap.sh` + `hooks/hooks.json` (uv venv bootstrap), and
  `tests/`.
- `plugins/memory/` ships a provider-neutral skill/commands, a standard-library
   validator/adapter, and Claude hooks that remain inert until explicitly enabled.
- `.github/copilot-instructions.md` — contributor guidance for keeping the
  repository's skills portable to GitHub Copilot.
