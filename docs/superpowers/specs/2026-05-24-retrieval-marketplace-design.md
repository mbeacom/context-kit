# Design: `productivity-skills` Retrieval Marketplace — Phase 1

- **Date:** 2026-05-24
- **Author:** Mark Beacom
- **Status:** Approved (pending written-spec review)
- **Repo:** `github.com/mbeacom/productivity-skills` (currently: README, LICENSE (MIT), .gitignore)

## Summary

Turn the empty `productivity-skills` repo into a **Claude Code plugin marketplace**
organized around a single idea: **information retrieval for agents across
complementary modalities** (lexical, structural, structured-data, history,
semantic/RAG, graph). Modalities are not rivals — an agent selects and *composes*
them based on what it knows about the query and the corpus.

Phase 1 delivers the marketplace skeleton plus two fully-built plugins
(`retrieval-core`, `code-search`), scaffolds two deferred plugins
(`local-rag`, `obsidian`) as stubs, and generates a contributor-facing
`CLAUDE.md`/`AGENTS.md` via `/init`. RAG and Obsidian get their own spec →
plan → implementation cycles later.

### Reference, not source

The upstream `netresearch/file-search-skill` (MIT code + CC-BY-SA-4.0 content)
was audited and is clean. It is used **only as a mindful reference**. All content
in this repo is **written fresh and licensed MIT** — no upstream text is copied,
so CC-BY-SA-4.0 share-alike never attaches. We intentionally improve on it:
better architecture, more modalities, a routing agent, and structured-data /
history / data-file coverage the upstream skill lacks.

## Goals

- Establish marketplace conventions (per Anthropic plugin/marketplace best
  practices) that future plugins slot into without restructuring.
- Ship a better-architected code/file search capability than the upstream
  reference, covering all tool groups selected: lexical, structural,
  structured-data (jq/yq/gron), history (git pickaxe + diff), structured rewrite
  (comby), data files (duckdb/sqlite-utils), metrics, and non-code docs.
- Provide a shared **retrieval-strategist** agent + decision-flow skill (the
  "spine") that routes/composes modalities — including hybrid retrieval that
  feeds the future RAG layer.
- Leave clean, documented sockets for `local-rag` (turbovec + ollama) and
  `obsidian`.

## Non-Goals (this phase)

- Building the RAG indexer/query pipeline or Obsidian skill logic (stubs only).
- Importing or porting any upstream code/content.
- Installing missing CLI tools as part of the plugin (we detect + document).

## Key Concept: Retrieval Modalities

The marketplace's organizing spine. An agent picks a modality by **what it knows
about the query × what it knows about the corpus**:

| Modality            | Tools                                   | Use when you know…                                    |
| ------------------- | --------------------------------------- | ----------------------------------------------------- |
| Lexical             | `rg`, `fd`                              | the exact token / regex / filename                    |
| Structural          | `ast-grep` (`sg`), `semgrep`            | the code *shape*, not the literal text                |
| Structured-data     | `jq`, `yq`, `gron`                      | the *schema* (JSON / YAML / config)                   |
| History             | `git log -S/-G/-L`, `difftastic`        | *when / why* something changed                        |
| Data files          | `duckdb`, `sqlite-utils`                | tabular corpora (CSV / Parquet / JSON at scale)       |
| Metrics             | `tokei`, `scc`                          | size / complexity of a codebase                       |
| Non-code docs       | `rga`, `pandoc`, `pdftotext`            | content inside PDFs / Office docs / archives          |
| Semantic (RAG)      | `turbovec` + `ollama` embeddings        | only the *meaning/intent*; corpus huge/unfamiliar/prose |
| Graph               | Obsidian wikilinks / backlinks / tags   | the corpus has human-authored *relationships*         |

**Composition (the real value).** turbovec's `search(query, k, allowlist=...)`
is built for hybrid retrieval: another system narrows to candidate ids, then
vectors rerank. So modalities layer:

- lexical / structured-data narrows → turbovec reranks semantically;
- Obsidian backlinks scope a subgraph → RAG searches within it;
- RAG surfaces candidate regions → `rg` pins exact lines.

## Architecture: Approach A — Modality plugins + shared core

```
productivity-skills/
├── .claude-plugin/
│   └── marketplace.json              # catalog; metadata.pluginRoot = "./plugins"
├── plugins/
│   ├── retrieval-core/               # the spine (BUILT)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/
│   │   │   └── retrieval-strategist.md
│   │   ├── skills/
│   │   │   └── retrieval-strategy/
│   │   │       └── SKILL.md
│   │   ├── LICENSE  CHANGELOG.md  README.md
│   ├── code-search/                  # our own, fresh MIT (BUILT)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   │   ├── code-search/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── references/*.md
│   │   │   └── data-and-docs-search/
│   │   │       ├── SKILL.md
│   │   │       └── references/*.md
│   │   ├── scripts/check-tools.sh
│   │   ├── LICENSE  CHANGELOG.md  README.md
│   ├── local-rag/                    # STUB (not listed in catalog yet)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/local-rag/SKILL.md (stub)
│   │   └── README.md
│   └── obsidian/                     # STUB (not listed in catalog yet)
│       ├── .claude-plugin/plugin.json
│       ├── skills/obsidian/SKILL.md  (stub)
│       └── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── superpowers/specs/2026-05-24-retrieval-marketplace-design.md
├── .github/workflows/                # validate, lint
├── .pre-commit-config.yaml
├── CLAUDE.md                          # via /init (contributor guide)
├── README.md  LICENSE  .gitignore
```

### marketplace.json

Located at repo root `.claude-plugin/marketplace.json`.

```json
{
  "name": "productivity-skills",
  "owner": { "name": "Mark Beacom" },
  "metadata": { "pluginRoot": "./plugins" },
  "plugins": [
    { "name": "retrieval-core", "source": "retrieval-core",
      "category": "retrieval", "tags": ["agent", "router", "search", "rag"] },
    { "name": "code-search", "source": "code-search",
      "category": "retrieval", "tags": ["ripgrep", "ast-grep", "search", "code"] }
  ]
}
```

- `metadata.pluginRoot: "./plugins"` lets `source` be the bare plugin name.
- Only the **two ready plugins** are listed. `local-rag` and `obsidian` dirs
  exist on disk but are **omitted from the catalog** until their specs ship, so
  no broken installs.

### Per-plugin `plugin.json` conventions

Every manifest at `.claude-plugin/plugin.json` includes:
`$schema`, `name` (kebab-case), `displayName`, `version` (semver — bump to ship
updates), `description`, `author`, `homepage`, `repository`, `license: "MIT"`,
`keywords`. Components live at the **plugin root** (`skills/`, `agents/`), never
inside `.claude-plugin/`.

## Plugin: `retrieval-core` (the spine)

### `agents/retrieval-strategist.md`

A subagent that selects and sequences retrieval modalities.

- Frontmatter: `name: retrieval-strategist`, `description` (when to invoke:
  "open-ended 'where/how is X' retrieval questions spanning lexical/structural/
  semantic/graph, or when a search strategy is unclear"), `model: sonnet`,
  `effort: medium`, `tools: Grep, Glob, Read, Bash` (read-oriented; no
  Write/Edit), `skills:` referencing `code-search` / `data-and-docs-search` /
  (future) `local-rag` / `obsidian` so it can dispatch into them.
- System prompt encodes: the modality table, the query×corpus decision flow, and
  the composition recipes (hybrid allowlist, RAG→rg pin, graph→RAG scope).
  Must **degrade gracefully** when a referenced skill/plugin isn't installed
  (suggest, don't assume).

### `skills/retrieval-strategy/SKILL.md`

The doc form of the routing logic — the modality table + decision flow +
composition patterns. Shared reference for both the agent and humans. Concise
(progressive disclosure; details deferred to each plugin's skills).

## Plugin: `code-search` (our own)

Declares `dependencies: ["retrieval-core"]` so installing it pulls the router.
Two skills, split by corpus to balance coverage against always-on token cost:

### `skills/code-search/SKILL.md` (+ `references/`)

Code-centric modalities:

- **Lexical** — `rg`, `fd` (text, regex, filenames; count-first; type scoping).
- **Structural** — `ast-grep` (`sg`) patterns/rewrite; `semgrep` rule packs / taint.
- **History** — `git log -S` / `-G` (pickaxe) / `-L` (line range); optional
  `difftastic` for structural diffs. ("When/why did this change.")
- **Structured rewrite** — `comby` (multi-language) and `sg --rewrite`.
- **Metrics** — `tokei`, `scc` (size, complexity, COCOMO).

`references/` holds one file per tool family (recipes, flags, gotchas), loaded on
demand. SKILL.md stays a tight tool-selection + decision-flow guide with an
`allowed-tools` frontmatter list scoped to these binaries plus Read/Glob/Grep.

### `skills/data-and-docs-search/SKILL.md` (+ `references/`)

Data / prose modalities:

- **Structured-data** — `jq` (JSON), `yq` (YAML/XML/TOML), `gron` (flatten JSON
  to greppable lines so `rg` can search it).
- **Data files** — `duckdb`, `sqlite-utils` (SQL over CSV/Parquet/JSON at scale).
- **Non-code docs** — `rga`, `pandoc`, `pdftotext` (PDFs, Office docs, archives).

### `scripts/check-tools.sh`

Reports tool presence and prints `brew install` hints for missing ones.
Current host state (2026-05-24): **present** — rg, fd, sg, ast-grep, semgrep,
rga, tokei, scc, jq, pandoc, pdftotext, ctags, gh, curl, ollama; **missing** —
yq, gron, comby, duckdb, sqlite-utils, difftastic. Skills declare these as
**optional** and degrade gracefully (recommend, don't require).

## Deferred stubs (vision captured; designed in their own specs)

### `local-rag` (stub)

Intended: `turbovec` (pip; vector index, MIT) + **ollama** local embeddings for a
fully-local/air-gapped RAG stack. Ships a `bin/rag` CLI (`index <path>`,
`query <text>`), persists the `.tvim` index under `${CLAUDE_PLUGIN_DATA}`, and
exposes the hybrid `allowlist` path so the strategist can feed it candidate ids
from lexical/structured/graph layers. **Open question for its spec:** primary
corpus (markdown notes / code / mixed).

### `obsidian` (stub)

Intended: Obsidian vault conventions (wikilinks, frontmatter, tags, MOCs, daily
notes, callouts) + link-graph traversal (backlinks, resolve `[[wikilinks]]`) that
can scope/feed RAG and search. **Open question for its spec:** authoring vs
retrieval vs both.

Each stub ships a valid `plugin.json`, a README stating intended scope + "not yet
released", and a placeholder `SKILL.md`. Not listed in `marketplace.json`.

## CI / Best Practices

- **Validation:** `claude plugin validate --strict` for each plugin in CI
  (catches manifest/frontmatter/hook schema errors and unrecognized fields).
- **Linting:** markdownlint, actionlint (workflows), shellcheck (scripts).
- **Pre-commit:** `.pre-commit-config.yaml` mirroring CI (pinned revs).
- **Versioning:** semver in each `plugin.json`; per-plugin `CHANGELOG.md`; bump
  `version` to ship updates (otherwise the cache key doesn't change).
- **Editor support:** `$schema` in every manifest.

## `/init`

After the skeleton lands, run `/init` to generate a repo-level
`CLAUDE.md`/`AGENTS.md`: a **contributor guide** (how to add a plugin, the
modality conventions, validation/lint commands, directory layout). Note: a
plugin-root `CLAUDE.md` is **not** auto-loaded into context — this file is for
repo maintainers, and plugins contribute context via skills/agents instead.

## Build Sequence (for the implementation plan)

1. Marketplace scaffold: `.claude-plugin/marketplace.json`, `plugins/` tree,
   root README/LICENSE/.gitignore touch-ups, `docs/ARCHITECTURE.md`.
2. `retrieval-core`: manifest → `retrieval-strategy` SKILL.md →
   `retrieval-strategist` agent.
3. `code-search`: manifest (with `dependencies`) → `code-search` SKILL.md +
   references → `data-and-docs-search` SKILL.md + references →
   `scripts/check-tools.sh`.
4. Stubs: `local-rag` and `obsidian` manifests + READMEs + SKILL stubs (omit
   from catalog).
5. CI + pre-commit: validate/lint workflows, `.pre-commit-config.yaml`.
6. `/init` to generate the contributor `CLAUDE.md`/`AGENTS.md`.
7. Validate locally (`claude plugin validate --strict ./plugins/*`), commit.

## Open Questions (deferred to future specs)

- `local-rag` corpus: notes / code / mixed?
- `obsidian` scope: authoring / retrieval / both?
- Embedding model + dim/bit-width defaults for turbovec (depends on corpus).

## Risks / Mitigations

- **Always-on token cost** of many skills → mitigated by 2 skills + progressive
  disclosure via `references/`. Revisit splitting only if a skill grows large.
- **Missing CLI tools** on consumer machines → `check-tools.sh` + optional-deps
  framing; skills never hard-fail on an absent optional tool.
- **Router referencing uninstalled plugins** → strategist degrades gracefully
  and suggests installs.
- **Version-bump discipline** → document in CONTRIBUTING/CLAUDE.md; CI reminder.
