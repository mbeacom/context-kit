# Architecture

`context-kit` is a Claude Code **plugin marketplace** and a
GitHub Copilot-compatible **Agent Skills** pack for **context engineering**. Its
spine is organized around **retrieval modalities** — complementary ways an agent
finds information, selected by what it knows about the query and the corpus, and
composed together — surrounded by plugins for orchestration (`plan-execute`),
steering (`context-steering`), verification (`verify`), and authoring
(`plugin-forge`).

Both hosts install the same plugins directly from the marketplace: Claude Code via
`/plugin`, GitHub Copilot CLI via `copilot plugin`. The retrieval instructions in
each `SKILL.md` are identical across hosts.

## Modalities

| Modality        | Tools                              | Use when you know…                          |
| --------------- | ---------------------------------- | ------------------------------------------- |
| Lexical         | `rg`, `fd`                         | the exact token / regex / filename          |
| Structural      | `ast-grep`, `semgrep`              | the code *shape*, not the literal text      |
| Structured-data | `jq`, `yq`, `gron`                 | the *schema* (JSON / YAML / config)         |
| History         | `git log -S/-G/-L`, `difftastic`   | *when / why* something changed              |
| Data files      | `duckdb`, `sqlite-utils`           | tabular corpora (CSV / Parquet / JSON)      |
| Metrics         | `tokei`, `scc`                     | size / complexity of a codebase             |
| Non-code docs   | `rga`, `pandoc`, `pdftotext`       | content in PDFs / Office docs / archives    |
| Semantic (RAG)  | `turbovec` + `ollama`              | only the meaning/intent; large/prose corpus |
| Graph           | Obsidian wikilinks / backlinks     | human-authored relationships                |

Modalities **compose**: lexical/structured narrows → vectors rerank
(turbovec `allowlist`); graph backlinks scope a subgraph → RAG within it;
RAG surfaces regions → `rg` pins exact lines.

## Plugins

| Plugin           | Status   | Purpose                                                    |
| ---------------- | -------- | ---------------------------------------------------------- |
| `retrieval-core` | shipped  | Routing agent + decision-flow skill (the spine)            |
| `code-search`    | shipped  | Lexical/structural/data/history/rewrite/metrics/doc search |
| `local-rag`      | shipped  | Local semantic RAG: `bin/rag` CLI (turbovec + ollama)      |
| `obsidian`       | shipped  | Skill-only RAG bridge: vault graph/tags → `rag query --allowlist` |
| `plan-execute`   | shipped  | Plan-big/execute-small orchestration: planner + cheap `execution-worker` |
| `context-steering` | shipped | Skill-only: place guidance at the cheapest layer (memory/rules/skills/subagents/hooks) |
| `verify`         | shipped  | Read-only `verifier` subagent + `verify-before-trust` skill; per-claim verdicts |
| `plugin-forge`   | shipped  | Author portable plugins: skill + `/scaffold-plugin` + manifest-drift validator |

`code-search` and `verify` declare `dependencies: ["retrieval-core"]`.
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

`local-rag` keeps everything local: ollama for embeddings, turbovec for the index
(persisted under `${CONTEXT_KIT_DATA}` or, in Claude Code,
`${CLAUDE_PLUGIN_DATA}`), nothing leaves the machine. The markdown loader is the
first-class path, but the indexer is built behind a pluggable loader interface so
other corpora (code, PDFs) can be added without a redesign.

## Agent host compatibility

| Host | What it uses | Notes |
| ---- | ------------ | ----- |
| Claude Code | `.claude-plugin/marketplace.json`, per-plugin manifests, hooks, `CLAUDE_PLUGIN_*` env vars | Install/update via `/plugin` commands. |
| GitHub Copilot | the same marketplace, via `copilot plugin marketplace add` + `copilot plugin install` | Installs plugins (skills, agents, commands) directly; run the local CLIs yourself. |

Portable examples should prefer `CONTEXT_KIT_*` environment variables,
with `CLAUDE_PLUGIN_*` documented as the Claude plugin fallback. See
[GITHUB_COPILOT.md](GITHUB_COPILOT.md) for a concrete Copilot setup.

## Layout

- `.claude-plugin/marketplace.json` — catalog (lists shipped plugins only).
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/skills/<name>/SKILL.md` — skills (with `references/` for detail).
- `plugins/<name>/agents/<name>.md` — subagents.
- `plugins/local-rag/` also ships `bin/rag` (CLI), `src/local_rag/` (Python
  package), `scripts/bootstrap.sh` + `hooks/hooks.json` (uv venv bootstrap), and
  `tests/`.
- `.github/copilot-instructions.md` — contributor guidance for keeping the
  repository's skills portable to GitHub Copilot.
