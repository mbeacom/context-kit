# Retrieval Marketplace — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the empty `productivity-skills` repo into a Claude Code plugin marketplace organized around retrieval modalities, shipping `retrieval-core` + `code-search` and scaffolding `local-rag` + `obsidian` stubs.

**Architecture:** Approach A — modality plugins + a shared core. `retrieval-core` holds a routing agent and a decision-flow skill (the spine). `code-search` (fresh MIT, two skills) covers lexical/structural/structured-data/history/rewrite/metrics/data-file/doc search and depends on `retrieval-core`. `local-rag` (turbovec+ollama) and `obsidian` are scaffolded but omitted from the catalog until their own specs ship.

**Tech Stack:** Claude Code plugins (`.claude-plugin/plugin.json`, `marketplace.json`, `skills/`, `agents/`), Markdown skills, Bash scripts, GitHub Actions, pre-commit. Verification via `claude plugin validate --strict`, shellcheck, markdownlint (through pre-commit).

**Spec:** `docs/superpowers/specs/2026-05-24-retrieval-marketplace-design.md`

**Conventions for every task:**
- All paths relative to repo root `/Users/markbeacom/github/mbeacom/productivity-skills`.
- Component dirs (`skills/`, `agents/`) live at the **plugin root**, never inside `.claude-plugin/`.
- Manifests carry `$schema`, `name`, `displayName`, `version`, `description`, `author`, `repository`, `license: "MIT"`, `keywords`.
- Commit after each task with the message shown.

---

## Task 1: Marketplace scaffold

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/.gitkeep` (placeholder until plugin dirs land)
- Create: `docs/ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Create the marketplace catalog**

Create `.claude-plugin/marketplace.json`:

```json
{
  "name": "productivity-skills",
  "owner": {
    "name": "Mark Beacom"
  },
  "metadata": {
    "description": "Retrieval-focused Claude Code plugins: search modalities, a routing agent, and (soon) local RAG and Obsidian.",
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "retrieval-core",
      "source": "retrieval-core",
      "category": "retrieval",
      "tags": ["agent", "router", "search", "rag", "retrieval"]
    },
    {
      "name": "code-search",
      "source": "code-search",
      "category": "retrieval",
      "tags": ["ripgrep", "ast-grep", "semgrep", "jq", "search", "code"]
    }
  ]
}
```

- [ ] **Step 2: Keep the plugins directory tracked**

Create empty file `plugins/.gitkeep` (removed in later tasks once real plugin dirs exist).

- [ ] **Step 3: Write docs/ARCHITECTURE.md**

Create `docs/ARCHITECTURE.md` with this content:

```markdown
# Architecture

`productivity-skills` is a Claude Code **plugin marketplace** organized around
**retrieval modalities** — complementary ways an agent finds information,
selected by what it knows about the query and the corpus, and composed together.

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
| `retrieval-core` | shipped  | Routing agent + decision-flow skill (the spine)           |
| `code-search`    | shipped  | Lexical/structural/data/history/rewrite/metrics/doc search |
| `local-rag`      | planned  | turbovec + ollama local RAG (own spec)                     |
| `obsidian`       | planned  | Vault conventions + link-graph retrieval (own spec)        |

## Layout

- `.claude-plugin/marketplace.json` — catalog (lists shipped plugins only).
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest.
- `plugins/<name>/skills/<name>/SKILL.md` — skills (with `references/` for detail).
- `plugins/<name>/agents/<name>.md` — subagents.

See `docs/superpowers/specs/` for the design history.
```

- [ ] **Step 4: Update README.md**

Replace `README.md` contents with a marketplace intro: a one-paragraph
description, an "Install" section with the two fenced commands
(`/plugin marketplace add mbeacom/productivity-skills` and
`/plugin install code-search@productivity-skills`), a note that `code-search`
pulls in `retrieval-core` automatically, a "Plugins" bullet list (retrieval-core,
code-search, and the two *planned* stubs), a link to `docs/ARCHITECTURE.md`, and a
"License" line: `MIT © Mark Beacom. Each plugin ships its own LICENSE.`

- [ ] **Step 5: Append plugin ignores to .gitignore**

Append to `.gitignore`:

```
# Claude Code plugin cache / local validation
.claude/
*.tq
*.tvim
```

- [ ] **Step 6: Validate JSON and commit**

Run: `python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); print('marketplace.json OK')"`
Expected: `marketplace.json OK`

```bash
git add .claude-plugin/marketplace.json plugins/.gitkeep docs/ARCHITECTURE.md README.md .gitignore
git commit -m "feat: scaffold marketplace catalog and architecture docs"
```

---

## Task 2: retrieval-core manifest

**Files:**
- Create: `plugins/retrieval-core/.claude-plugin/plugin.json`
- Create: `plugins/retrieval-core/LICENSE`
- Create: `plugins/retrieval-core/CHANGELOG.md`
- Create: `plugins/retrieval-core/README.md`

- [ ] **Step 1: Write the manifest**

Create `plugins/retrieval-core/.claude-plugin/plugin.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "retrieval-core",
  "displayName": "Retrieval Core",
  "version": "0.1.0",
  "description": "A retrieval-strategist agent and decision-flow skill that pick and compose search modalities (lexical, structural, semantic/RAG, graph).",
  "author": { "name": "Mark Beacom" },
  "homepage": "https://github.com/mbeacom/productivity-skills",
  "repository": "https://github.com/mbeacom/productivity-skills",
  "license": "MIT",
  "keywords": ["retrieval", "search", "router", "agent", "rag"]
}
```

- [ ] **Step 2: Add LICENSE**

Create `plugins/retrieval-core/LICENSE` — copy the repo-root `LICENSE` (MIT, Mark Beacom, 2026) verbatim.

Run: `cp LICENSE plugins/retrieval-core/LICENSE`

- [ ] **Step 3: Add CHANGELOG**

Create `plugins/retrieval-core/CHANGELOG.md`:

```markdown
# Changelog

## 0.1.0 — 2026-05-24

- Initial release: `retrieval-strategist` agent and `retrieval-strategy` skill.
```

- [ ] **Step 4: Add README**

Create `plugins/retrieval-core/README.md`:

```markdown
# Retrieval Core

The spine of the `productivity-skills` marketplace. Provides:

- **`retrieval-strategist`** (agent) — picks and sequences retrieval modalities,
  including hybrid composition (lexical/structured narrows → vectors rerank).
- **`retrieval-strategy`** (skill) — the decision-flow reference both the agent
  and humans use.

Install standalone, or get it automatically by installing `code-search`.

MIT © Mark Beacom.
```

- [ ] **Step 5: Validate and commit**

Run: `claude plugin validate ./plugins/retrieval-core --strict`
Expected: validation passes (no skills/agents yet is OK; `name` present).

```bash
git rm -q plugins/.gitkeep
git add plugins/retrieval-core
git commit -m "feat(retrieval-core): add plugin manifest and metadata"
```

---

## Task 3: retrieval-core — `retrieval-strategy` skill

**Files:**
- Create: `plugins/retrieval-core/skills/retrieval-strategy/SKILL.md`

- [ ] **Step 1: Write the skill**

Create `plugins/retrieval-core/skills/retrieval-strategy/SKILL.md`:

```markdown
---
name: retrieval-strategy
description: "Use when deciding HOW to find information — choosing or composing search modalities (lexical, structural, structured-data, history, semantic/RAG, graph) for a query and corpus."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Glob Grep Bash
---

# Retrieval Strategy

Pick a modality by **what you know about the query × what you know about the corpus.**

## Decision flow

- Know the exact token / regex / filename? → **lexical** (`rg`, `fd`)
- Know the code *shape*, not the text? → **structural** (`ast-grep`, `semgrep`)
- Querying JSON / YAML / config by schema? → **structured-data** (`jq`, `yq`, `gron`)
- Asking *when/why* something changed? → **history** (`git log -S/-G/-L`)
- Tabular data at scale (CSV/Parquet)? → **data files** (`duckdb`, `sqlite-utils`)
- Sizing / complexity of a codebase? → **metrics** (`tokei`, `scc`)
- Content inside PDFs / Office docs / archives? → **docs** (`rga`, `pandoc`)
- Only know the *meaning/intent*, or corpus is huge / unfamiliar / prose? →
  **semantic / RAG** (`local-rag`: turbovec + ollama)
- Corpus is a human-authored link graph? → **graph** (`obsidian`)

Lexical/structural/structured-data/history/metrics/docs live in **code-search**.
Semantic and graph live in **local-rag** and **obsidian** (install separately).

## Composition (modalities are layers, not rivals)

- **Hybrid rerank:** lexical or structured-data produces a candidate set →
  semantic reranks it (turbovec search with an `allowlist` of candidate ids).
- **Scope then search:** graph backlinks narrow to a subgraph → RAG within it.
- **Find then pin:** RAG surfaces candidate regions → `rg` pins exact lines.

## Defaults

1. Start with the cheapest modality that fits (lexical is free and instant).
2. Narrow before widening; count matches (`rg -c`) before reading full output.
3. Escalate to semantic only when lexical/structural genuinely can't express the
   query (intent without known terms) or the corpus is too large/unfamiliar.
4. If a needed plugin (`local-rag`, `obsidian`) isn't installed, say so and
   suggest installing it — don't assume its tools exist.
```

- [ ] **Step 2: Validate and commit**

Run: `claude plugin validate ./plugins/retrieval-core --strict`
Expected: passes; skill `retrieval-strategy` discovered.

```bash
git add plugins/retrieval-core/skills/retrieval-strategy/SKILL.md
git commit -m "feat(retrieval-core): add retrieval-strategy decision-flow skill"
```

---

## Task 4: retrieval-core — `retrieval-strategist` agent

**Files:**
- Create: `plugins/retrieval-core/agents/retrieval-strategist.md`

- [ ] **Step 1: Write the agent**

Create `plugins/retrieval-core/agents/retrieval-strategist.md`:

```markdown
---
name: retrieval-strategist
description: Use for open-ended "where/how is X handled" retrieval questions that span multiple search modalities, or when the right search strategy is unclear. Plans and sequences lexical, structural, structured-data, history, semantic (RAG), and graph search, and composes them (hybrid rerank, scope-then-search, find-then-pin). Read-only; reports findings and the strategy used.
model: sonnet
effort: medium
tools: Grep, Glob, Read, Bash
skills: retrieval-strategy
---

You are the retrieval-strategist. Your job is to FIND information efficiently by
choosing and composing search modalities — not to edit code.

## Method

1. Clarify the query in terms of: what is known (exact terms? code shape?
   intent only?) and the corpus (this repo? data files? PDFs? a notes vault? a
   large/unfamiliar codebase?).
2. Consult the `retrieval-strategy` skill's decision flow and pick the cheapest
   modality that fits. Prefer lexical (`rg`/`fd`) first; it is free and instant.
3. Execute searches with the relevant CLI tools via Bash. Always:
   - scope by type/dir (`rg -t`, `--lang`, `fd -e`), count first (`rg -c`),
   - exclude noise (`-g '!vendor/'`, `fd -E node_modules`),
   - run independent queries in parallel, never sequential `&&` chains.
4. Compose when one modality is insufficient:
   - **Hybrid rerank** — lexical/structured-data yields candidates → hand the
     candidate set to semantic search to rerank by meaning.
   - **Scope then search** — graph backlinks narrow scope → search within it.
   - **Find then pin** — semantic surfaces a region → `rg` pins exact lines.
5. Stop when you can answer; report the answer, the exact locations
   (`path:line`), and the strategy/tools you used.

## Constraints

- Read-only: never Write or Edit. You investigate and report.
- The semantic (`local-rag`) and graph (`obsidian`) modalities are separate
  plugins. If they are not installed, do not fabricate their tools — say which
  plugin would help and proceed with the modalities you do have.
- Detect missing optional CLI tools gracefully; suggest install, don't crash.
```

- [ ] **Step 2: Validate and commit**

Run: `claude plugin validate ./plugins/retrieval-core --strict`
Expected: passes; agent `retrieval-strategist` discovered.

```bash
git add plugins/retrieval-core/agents/retrieval-strategist.md
git commit -m "feat(retrieval-core): add retrieval-strategist routing agent"
```

---

## Task 5: code-search manifest (with dependency)

**Files:**
- Create: `plugins/code-search/.claude-plugin/plugin.json`
- Create: `plugins/code-search/LICENSE`
- Create: `plugins/code-search/CHANGELOG.md`
- Create: `plugins/code-search/README.md`

- [ ] **Step 1: Write the manifest**

Create `plugins/code-search/.claude-plugin/plugin.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "code-search",
  "displayName": "Code Search",
  "version": "0.1.0",
  "description": "Fast CLI search across modalities: lexical (rg/fd), structural (ast-grep/semgrep), structured-data (jq/yq/gron), history (git pickaxe), structured rewrite (comby), data files (duckdb), metrics (tokei/scc), and non-code docs (rga/pandoc).",
  "author": { "name": "Mark Beacom" },
  "homepage": "https://github.com/mbeacom/productivity-skills",
  "repository": "https://github.com/mbeacom/productivity-skills",
  "license": "MIT",
  "keywords": ["ripgrep", "ast-grep", "semgrep", "fd", "jq", "search", "code", "rga"],
  "dependencies": ["retrieval-core"]
}
```

- [ ] **Step 2: LICENSE / CHANGELOG / README**

```bash
cp LICENSE plugins/code-search/LICENSE
```

Create `plugins/code-search/CHANGELOG.md`:

```markdown
# Changelog

## 0.1.0 — 2026-05-24

- Initial release: `code-search` and `data-and-docs-search` skills, `check-tools.sh`.
```

Create `plugins/code-search/README.md`:

```markdown
# Code Search

Fast, modern CLI search for agents, covering complementary modalities:

- **`code-search`** — lexical (`rg`, `fd`), structural (`ast-grep`, `semgrep`),
  history (`git log -S/-G/-L`, `difftastic`), structured rewrite (`comby`),
  metrics (`tokei`, `scc`).
- **`data-and-docs-search`** — structured-data (`jq`, `yq`, `gron`), data files
  (`duckdb`, `sqlite-utils`), non-code docs (`rga`, `pandoc`, `pdftotext`).

Depends on `retrieval-core` (auto-installed). Run `scripts/check-tools.sh` to see
which tools are present and how to install the rest.

MIT © Mark Beacom.
```

- [ ] **Step 3: Validate and commit**

Run: `claude plugin validate ./plugins/code-search --strict`
Expected: passes; `name` present, `dependencies` recognized.

```bash
git add plugins/code-search/.claude-plugin/plugin.json plugins/code-search/LICENSE plugins/code-search/CHANGELOG.md plugins/code-search/README.md
git commit -m "feat(code-search): add plugin manifest with retrieval-core dependency"
```

---

## Task 6: code-search — `code-search` skill + references

**Files:**
- Create: `plugins/code-search/skills/code-search/SKILL.md`
- Create: `plugins/code-search/skills/code-search/references/ripgrep.md`
- Create: `plugins/code-search/skills/code-search/references/fd.md`
- Create: `plugins/code-search/skills/code-search/references/ast-grep.md`
- Create: `plugins/code-search/skills/code-search/references/semgrep.md`
- Create: `plugins/code-search/skills/code-search/references/git-history.md`
- Create: `plugins/code-search/skills/code-search/references/comby.md`
- Create: `plugins/code-search/skills/code-search/references/metrics.md`

- [ ] **Step 1: Write SKILL.md**

Create `plugins/code-search/skills/code-search/SKILL.md`:

```markdown
---
name: code-search
description: "Use when searching source code: text/regex (ripgrep), structural/AST patterns (ast-grep, semgrep), when/why code changed (git history), structural rewrites (comby), or codebase size/complexity (tokei, scc)."
license: MIT
compatibility: "Requires ripgrep (rg). Optional: fd, ast-grep (sg), semgrep, comby, difftastic, tokei, scc."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(rg:*) Bash(fd:*) Bash(sg:*) Bash(ast-grep:*) Bash(semgrep:*) Bash(git:*) Bash(comby:*) Bash(difft:*) Bash(tokei:*) Bash(scc:*) Read Glob Grep
---

# Code Search

CLI search for source code. Pick the modality by what you know.

| Task                              | Use                  | Reference                       |
| --------------------------------- | -------------------- | ------------------------------- |
| Text / regex in code              | `rg`                 | [ripgrep](references/ripgrep.md) |
| Find files by name/path           | `fd`                 | [fd](references/fd.md)           |
| Structural / syntax-aware search  | `sg` (ast-grep)      | [ast-grep](references/ast-grep.md) |
| Security/lint rule packs, taint   | `semgrep`            | [semgrep](references/semgrep.md) |
| When/why code changed             | `git log -S/-G/-L`   | [git-history](references/git-history.md) |
| Structural search-and-replace     | `comby`, `sg --rewrite` | [comby](references/comby.md)  |
| Size / complexity by language     | `tokei`, `scc`       | [metrics](references/metrics.md) |

**Decision flow:** text → `rg` | structural → `sg` | rule packs → `semgrep` |
filenames → `fd` | change history → `git` pickaxe | rewrite → `comby` | LOC → `tokei`.

## Best practices

1. **Start narrow** — scope by type (`rg -t py`, `sg --lang ts`, `fd -e go`),
   restrict dirs, and **count first** (`rg -c pattern | wc -l`) before reading.
2. **Exclude noise** — `rg -g '!vendor/' -g '!*.lock'`, `fd -E node_modules`.
3. **Batch independent queries** — union patterns (`rg -e P1 -e P2`) in one walk,
   or issue distinct searches as parallel tool calls. Never sequential `&&`.
4. **`rg -t ts` includes `.tsx`; `fd -e ts` does NOT** — use `fd -e ts -e tsx`.
5. For cross-modality strategy (semantic/graph, hybrid rerank), see the
   `retrieval-strategy` skill or invoke the `retrieval-strategist` agent.

For non-code corpora (JSON/YAML, CSV/Parquet, PDFs/Office), use the
`data-and-docs-search` skill.
```

- [ ] **Step 2: Write reference — ripgrep**

Create `references/ripgrep.md` with concrete recipes (each as a labeled `bash` block):
- type scoping (`rg -t py`, `-T test`), case (`-i`, `-S`), word/fixed (`-w`, `-F`).
- count-first workflow: `rg -c PATTERN` then `rg PATTERN path/`.
- context (`-A/-B/-C`), files-with-matches (`-l`), only-matching (`-o`).
- multiline (`-U`, `--multiline-dotall`), PCRE2 (`-P`) for lookarounds.
- globs (`-g '!vendor/'`, `-g '*.{ts,tsx}'`), hidden/no-ignore (`--hidden`, `-u`).
- union patterns (`-e A -e B`), replace preview (`-r`), `--json` for tooling.
- a "find committed credentials" example and a "TODO census" example.

- [ ] **Step 3: Write reference — fd**

Create `references/fd.md`:
- basic name/glob (`fd foo`, `fd -g '*.test.ts'`), extension (`-e ts -e tsx`).
- type (`-t f`, `-t d`, `-t l`), hidden/ignore (`-H`, `-I`), depth (`-d`).
- time filters (`--changed-within 1d`, `--changed-before`).
- exec (`-x` per-file, `-X` batched) e.g. `fd -e go -X rg 'func Test'`.
- exclude (`-E node_modules`), full-path (`-p`), the `rg -t` vs `fd -e` gotcha.

- [ ] **Step 4: Write reference — ast-grep**

Create `references/ast-grep.md`:
- pattern syntax: `$VAR` (single node), `$$$` (variadic), `--lang`.
- search: `sg -p 'logger.debug($$$)' --lang js`.
- rewrite: `sg -p 'logger.debug($$$A)' -r 'logger.info($$$A)' --lang js`.
- YAML rules (`sg scan -r rule.yml`), relational (`inside`, `has`).
- when to prefer `sg` over `rg` (structure, not text); per-language examples
  (Python def, TS import, Go func) — at least 4 languages.

- [ ] **Step 5: Write reference — semgrep**

Create `references/semgrep.md`:
- single pattern (`semgrep -e 'requests.get(...)' --lang python .`).
- registry/rule packs (`--config=auto`, `--config p/owasp-top-ten`).
- taint mode YAML rule example (source → sink) with a short rule file.
- when `semgrep` beats `sg`: catalogs of rules, taint, CI gating; SARIF output
  (`--sarif`). Note it is heavier/slower than `rg`/`sg`.

- [ ] **Step 6: Write reference — git-history**

Create `references/git-history.md`:
- pickaxe `git log -S'string'` (added/removed occurrences) vs `-G'regex'`.
- `git log -L :func:file` and `-L start,end:file` for line/function evolution.
- `git log -p -- path`, `git log --oneline -- path`, `git log -1 -S'x' -- path`.
- blame (`git blame -L`), `git log --diff-filter=D` (when deleted).
- optional `difftastic` (`GIT_EXTERNAL_DIFF=difft git show <sha>`) for structural diffs.
- examples: "when was this constant introduced", "who removed this call".

- [ ] **Step 7: Write reference — comby**

Create `references/comby.md`:
- hole syntax `:[name]`, match `comby 'logger.debug(:[args])' '' -matcher .js .`.
- rewrite: `comby 'foo(:[x])' 'bar(:[x])' .py -i` (note `-i` writes in place).
- `-d dir`, `-matcher`, dry-run default vs `-i`, `.lang` extension scoping.
- when to choose `comby` over `sg`: multi-language, lighter pattern syntax;
  note `sg --rewrite` as the AST-precise alternative.

- [ ] **Step 8: Write reference — metrics**

Create `references/metrics.md`:
- `tokei` (`tokei`, `tokei --sort code`, `tokei -o json`).
- `scc` (`scc`, `scc --wide` for complexity + COCOMO, `scc --by-file`).
- when to use which (tokei = fast LOC; scc = complexity/cost estimates).
- prefer these over `cloc`/`wc -l`.

- [ ] **Step 9: Validate and commit**

Run: `claude plugin validate ./plugins/code-search --strict`
Expected: passes; skill `code-search` discovered with references.

```bash
git add plugins/code-search/skills/code-search
git commit -m "feat(code-search): add code-search skill and tool references"
```

---

## Task 7: code-search — `data-and-docs-search` skill + references

**Files:**
- Create: `plugins/code-search/skills/data-and-docs-search/SKILL.md`
- Create: `plugins/code-search/skills/data-and-docs-search/references/jq-yq-gron.md`
- Create: `plugins/code-search/skills/data-and-docs-search/references/data-files.md`
- Create: `plugins/code-search/skills/data-and-docs-search/references/docs.md`

- [ ] **Step 1: Write SKILL.md**

Create `plugins/code-search/skills/data-and-docs-search/SKILL.md`:

```markdown
---
name: data-and-docs-search
description: "Use when searching non-code corpora: query JSON/YAML/config (jq, yq, gron), tabular data files (duckdb, sqlite-utils), or content inside PDFs/Office docs/archives (rga, pandoc, pdftotext)."
license: MIT
compatibility: "Optional tools: jq, yq, gron, duckdb, sqlite-utils, rga (ripgrep-all), pandoc, pdftotext."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(jq:*) Bash(yq:*) Bash(gron:*) Bash(duckdb:*) Bash(sqlite-utils:*) Bash(rga:*) Bash(pandoc:*) Bash(pdftotext:*) Bash(rg:*) Read Glob Grep
---

# Data & Docs Search

Search beyond source code.

| Corpus                         | Use                       | Reference                          |
| ------------------------------ | ------------------------- | ---------------------------------- |
| JSON                           | `jq`, or `gron` + `rg`    | [jq-yq-gron](references/jq-yq-gron.md) |
| YAML / TOML / XML              | `yq`                      | [jq-yq-gron](references/jq-yq-gron.md) |
| CSV / Parquet / JSON at scale  | `duckdb`, `sqlite-utils`  | [data-files](references/data-files.md) |
| PDFs / Office docs / archives  | `rga`, `pandoc`, `pdftotext` | [docs](references/docs.md)      |

**Decision flow:** known JSON path → `jq` | "grep this JSON" → `gron \| rg` |
YAML/TOML → `yq` | tabular/analytical → `duckdb` | inside PDFs/docs → `rga`.

## Best practices

1. `gron file.json | rg pattern` turns nested JSON into greppable lines — ideal
   when you don't know the exact path. `gron -u` reverses it.
2. `rga` is `rg` for non-text files; first run builds a cache, later runs are fast.
   Scope with `--rga-adapters` and the same globs as `rg`.
3. For analytical queries over CSV/Parquet, `duckdb` reads files directly:
   `duckdb -c "SELECT ... FROM 'data.parquet' ..."`.
4. These tools are optional — run `scripts/check-tools.sh` and install what's
   missing before relying on them.
```

- [ ] **Step 2: Write reference — jq-yq-gron**

Create `references/jq-yq-gron.md`:
- `jq`: field access (`.a.b`), arrays (`.[]`, `.[0]`), filters (`select(.x>1)`),
  map/keys, `-r` raw, `-c` compact, `to_entries`, `paths`; a "find all keys
  named X anywhere" recipe.
- `gron`: `gron file.json | rg 'token'`, then `gron -u` to rebuild; why it beats
  `jq` when the path is unknown.
- `yq`: YAML equivalents (`yq '.a.b' f.yaml`), `-p`/`-o` for TOML/XML/JSON
  conversion, multi-doc (`yq ea`). Note `yq` (mikefarah) syntax.

- [ ] **Step 3: Write reference — data-files**

Create `references/data-files.md`:
- `duckdb`: `duckdb -c "SELECT * FROM 'f.csv' LIMIT 5"`, read Parquet/JSON
  directly, `DESCRIBE`, aggregation, glob over many files (`'data/*.parquet'`).
- `sqlite-utils`: `sqlite-utils memory data.csv "select ..."`, insert/query a
  local db, `--csv`/`--json` output.
- when to use SQL over `jq`/`rg` (joins, aggregation, large tabular data).

- [ ] **Step 4: Write reference — docs**

Create `references/docs.md`:
- `rga`: `rga 'phrase' docs/`, supported formats (PDF, docx, xlsx, zip, sqlite,
  etc.), caching, `--rga-adapters=+pandoc`, same flags as `rg` (`-i`, `-l`, `-C`).
- `pdftotext`: `pdftotext file.pdf - | rg pattern` for quick PDF text.
- `pandoc`: convert to markdown for searching/reading
  (`pandoc f.docx -t markdown`).
- when to reach past `rga` (need layout/structure → `pandoc`).

- [ ] **Step 5: Validate and commit**

Run: `claude plugin validate ./plugins/code-search --strict`
Expected: passes; both `code-search` and `data-and-docs-search` skills discovered.

```bash
git add plugins/code-search/skills/data-and-docs-search
git commit -m "feat(code-search): add data-and-docs-search skill and references"
```

---

## Task 8: code-search — `check-tools.sh`

**Files:**
- Create: `plugins/code-search/scripts/check-tools.sh`

- [ ] **Step 1: Write the script**

Create `plugins/code-search/scripts/check-tools.sh` with this content (a Bash
array of `tool|purpose|brew-formula`, looping with `command -v` to print a status
table and a `brew install` line for anything missing, exiting non-zero if any are
missing):

```bash
#!/usr/bin/env bash
# check-tools.sh — report which code-search CLI tools are installed.
set -euo pipefail

# tool|purpose|brew formula
TOOLS=(
  "rg|lexical text search (required)|ripgrep"
  "fd|file finder|fd"
  "sg|structural search (ast-grep)|ast-grep"
  "semgrep|rule packs / taint|semgrep"
  "git|history / pickaxe (required)|git"
  "comby|structural rewrite|comby"
  "difft|structural diffs (difftastic)|difftastic"
  "tokei|LOC metrics|tokei"
  "scc|complexity metrics|scc"
  "jq|JSON query|jq"
  "yq|YAML/TOML/XML query|yq"
  "gron|greppable JSON|gron"
  "duckdb|SQL over data files|duckdb"
  "sqlite-utils|SQLite/CSV query|sqlite-utils"
  "rga|search PDFs/Office/archives|ripgrep-all"
  "pandoc|document conversion|pandoc"
  "pdftotext|PDF text extraction|poppler"
)

missing=()
printf "%-14s %-34s %s\n" "TOOL" "PURPOSE" "STATUS"
printf "%-14s %-34s %s\n" "----" "-------" "------"
for entry in "${TOOLS[@]}"; do
  IFS='|' read -r tool purpose formula <<<"$entry"
  if command -v "$tool" >/dev/null 2>&1; then
    printf "%-14s %-34s %s\n" "$tool" "$purpose" "present"
  else
    printf "%-14s %-34s %s\n" "$tool" "$purpose" "MISSING (brew install $formula)"
    missing+=("$formula")
  fi
done

if ((${#missing[@]})); then
  echo ""
  uniq_formulas=$(printf "%s\n" "${missing[@]}" | sort -u | tr '\n' ' ')
  echo "Install missing tools: brew install ${uniq_formulas}"
  exit 1
fi
echo ""
echo "All code-search tools present."
```

- [ ] **Step 2: Make executable, lint, run**

```bash
chmod +x plugins/code-search/scripts/check-tools.sh
```

Run: `bash plugins/code-search/scripts/check-tools.sh; echo "exit=$?"`
Expected: a table; exit=1 on this host (yq/gron/comby/duckdb/sqlite-utils/difft missing) with a `brew install` line. That is correct behavior.

If `shellcheck` is available: `shellcheck plugins/code-search/scripts/check-tools.sh` (expect no errors). Otherwise it runs in the pre-commit hook added in Task 11.

- [ ] **Step 3: Commit**

```bash
git add plugins/code-search/scripts/check-tools.sh
git commit -m "feat(code-search): add check-tools.sh tool-availability report"
```

---

## Task 9: `local-rag` stub

**Files:**
- Create: `plugins/local-rag/.claude-plugin/plugin.json`
- Create: `plugins/local-rag/README.md`
- Create: `plugins/local-rag/skills/local-rag/SKILL.md`
- Create: `plugins/local-rag/LICENSE`

- [ ] **Step 1: Manifest**

Create `plugins/local-rag/.claude-plugin/plugin.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "local-rag",
  "displayName": "Local RAG",
  "version": "0.0.1",
  "description": "PLANNED: fully-local semantic retrieval using turbovec (vector index) + ollama embeddings, with hybrid allowlist reranking. Not yet released.",
  "author": { "name": "Mark Beacom" },
  "homepage": "https://github.com/mbeacom/productivity-skills",
  "repository": "https://github.com/mbeacom/productivity-skills",
  "license": "MIT",
  "keywords": ["rag", "vector-search", "turbovec", "ollama", "embeddings", "semantic"]
}
```

- [ ] **Step 2: LICENSE / README / stub skill**

```bash
cp LICENSE plugins/local-rag/LICENSE
```

Create `plugins/local-rag/README.md`:

```markdown
# Local RAG (planned)

Fully-local semantic retrieval: [`turbovec`](https://github.com/RyanCodrai/turbovec)
(quantized vector index, MIT) + `ollama` embeddings. Will ship a `bin/rag` CLI
(`index <path>` / `query <text>`), persist the index under `${CLAUDE_PLUGIN_DATA}`,
and expose turbovec's hybrid `allowlist` path so `retrieval-core` can feed it
candidates from lexical/graph layers.

**Status:** scaffold only — not listed in the marketplace catalog yet. Design in
a forthcoming spec. Open question: primary corpus (notes / code / mixed).
```

Create `plugins/local-rag/skills/local-rag/SKILL.md`:

```markdown
---
name: local-rag
description: "PLANNED (not yet implemented): local semantic/RAG retrieval with turbovec + ollama. This is a scaffold placeholder."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.0.1"
  status: planned
---

# Local RAG (planned)

This plugin is a scaffold. Semantic retrieval is not implemented yet.

For now, use the `code-search` lexical/structural modalities, or the
`retrieval-strategy` skill to plan a search. When this ships it will provide
turbovec + ollama embedding-based search and hybrid reranking.
```

- [ ] **Step 3: Validate and commit**

Run: `claude plugin validate ./plugins/local-rag --strict`
Expected: passes (stub is a valid plugin; not in catalog).

```bash
git add plugins/local-rag
git commit -m "feat(local-rag): scaffold planned turbovec+ollama RAG plugin stub"
```

---

## Task 10: `obsidian` stub

**Files:**
- Create: `plugins/obsidian/.claude-plugin/plugin.json`
- Create: `plugins/obsidian/README.md`
- Create: `plugins/obsidian/skills/obsidian/SKILL.md`
- Create: `plugins/obsidian/LICENSE`

- [ ] **Step 1: Manifest**

Create `plugins/obsidian/.claude-plugin/plugin.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "obsidian",
  "displayName": "Obsidian",
  "version": "0.0.1",
  "description": "PLANNED: Obsidian vault conventions (wikilinks, frontmatter, tags, MOCs, daily notes, callouts) and link-graph retrieval that feeds RAG/search. Not yet released.",
  "author": { "name": "Mark Beacom" },
  "homepage": "https://github.com/mbeacom/productivity-skills",
  "repository": "https://github.com/mbeacom/productivity-skills",
  "license": "MIT",
  "keywords": ["obsidian", "markdown", "wikilinks", "notes", "knowledge-base", "graph"]
}
```

- [ ] **Step 2: LICENSE / README / stub skill**

```bash
cp LICENSE plugins/obsidian/LICENSE
```

Create `plugins/obsidian/README.md`:

```markdown
# Obsidian (planned)

Obsidian vault support: wikilinks (`[[note]]`), frontmatter, tags, MOCs, daily
notes, callouts — plus link-graph traversal (backlinks, link resolution) that can
scope and feed semantic search.

**Status:** scaffold only — not listed in the marketplace catalog yet. Design in
a forthcoming spec. Open question: scope (authoring / retrieval / both).
```

Create `plugins/obsidian/skills/obsidian/SKILL.md`:

```markdown
---
name: obsidian
description: "PLANNED (not yet implemented): Obsidian vault conventions and link-graph retrieval. This is a scaffold placeholder."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.0.1"
  status: planned
---

# Obsidian (planned)

This plugin is a scaffold. Vault conventions and link-graph retrieval are not
implemented yet. Use `code-search` for lexical search over markdown in the
meantime.
```

- [ ] **Step 3: Validate and commit**

Run: `claude plugin validate ./plugins/obsidian --strict`
Expected: passes.

```bash
git add plugins/obsidian
git commit -m "feat(obsidian): scaffold planned Obsidian vault plugin stub"
```

---

## Task 11: CI + pre-commit

**Files:**
- Create: `.github/workflows/validate.yml`
- Create: `.pre-commit-config.yaml`
- Create: `.markdownlint-cli2.jsonc`

- [ ] **Step 1: Validation workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: Validate

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  plugin-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code
      - name: Validate marketplace and plugins
        run: |
          for p in plugins/*/; do
            if [ -f "$p/.claude-plugin/plugin.json" ]; then
              echo "::group::validate $p"
              claude plugin validate "$p" --strict
              echo "::endgroup::"
            fi
          done

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Run pre-commit
        uses: pre-commit/action@v3.0.1
```

> Note: confirm the published CLI package name during execution. If
> `@anthropic-ai/claude-code` is not the correct global package, replace the
> install step with the official documented install command. The validation
> loop itself is package-agnostic.

- [ ] **Step 2: markdownlint config**

Create `.markdownlint-cli2.jsonc`:

```jsonc
{
  "config": {
    "default": true,
    "MD013": false,
    "MD033": false,
    "MD041": false
  },
  "globs": ["**/*.md"],
  "ignores": ["**/node_modules/**", ".git/**"]
}
```

- [ ] **Step 3: pre-commit config**

Create `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [pre-commit]
default_stages: [pre-commit]

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: check-json
      - id: check-yaml

  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.22.1
    hooks:
      - id: markdownlint-cli2
        files: '\.md$'

  - repo: https://github.com/shellcheck-py/shellcheck-py
    rev: v0.11.0.1
    hooks:
      - id: shellcheck
```

- [ ] **Step 4: Run pre-commit locally and fix findings**

Run: `pre-commit run --all-files`
Expected: hooks install and pass. Fix any trailing-whitespace / EOF / shellcheck
/ markdownlint findings they report, then re-run until green. (markdownlint may
flag earlier files — fix inline; do not disable rules beyond those in the config.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/validate.yml .pre-commit-config.yaml .markdownlint-cli2.jsonc
git commit -m "ci: add plugin validation workflow and pre-commit lint config"
```

---

## Task 12: `/init` — contributor guide

**Files:**
- Create: `CLAUDE.md` (generated by `/init`, then trimmed)

- [ ] **Step 1: Run /init**

In the Claude Code session, run the `/init` command to generate `CLAUDE.md`.

- [ ] **Step 2: Ensure it captures marketplace conventions**

Edit the generated `CLAUDE.md` so it includes (concise, contributor-facing):
- What this repo is (a Claude Code plugin marketplace; see `docs/ARCHITECTURE.md`).
- Layout: `.claude-plugin/marketplace.json`; `plugins/<name>/.claude-plugin/plugin.json`;
  components (`skills/`, `agents/`) at plugin root, never in `.claude-plugin/`.
- How to add a plugin: create dir + manifest, add skills/agents, add a catalog
  entry in `marketplace.json` **only when ready** (stubs stay unlisted).
- Validation/lint commands:
  - `claude plugin validate ./plugins/<name> --strict`
  - `pre-commit run --all-files`
  - `bash plugins/code-search/scripts/check-tools.sh`
- Versioning rule: bump `version` in each `plugin.json` to ship updates.
- The retrieval-modality convention (one line + link to ARCHITECTURE.md).

Keep it under ~150 lines (index style).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add contributor CLAUDE.md via /init"
```

---

## Task 13: Final validation pass

**Files:** none (verification only)

- [ ] **Step 1: Validate every plugin**

Run:
```bash
for p in plugins/*/; do
  [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict
done
```
Expected: all four plugins pass.

- [ ] **Step 2: Confirm marketplace lists only shipped plugins**

Run: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print([p['name'] for p in d['plugins']])"`
Expected: `['retrieval-core', 'code-search']` (stubs intentionally absent).

- [ ] **Step 3: Local install smoke test (optional but recommended)**

Run: `claude plugin marketplace add . 2>&1 || true` then `/plugin` to confirm
`retrieval-core` and `code-search` appear and `code-search` shows `retrieval-core`
as a dependency. (If running non-interactively, skip and note for manual check.)

- [ ] **Step 4: Final pre-commit + commit any fixes**

Run: `pre-commit run --all-files`
Expected: green. Commit any residual fixes:

```bash
git add -A
git commit -m "chore: final validation fixes for phase 1 marketplace" || echo "nothing to commit"
```

---

## Self-Review Notes (author)

- **Spec coverage:** marketplace structure (T1), retrieval-core agent+skill
  (T2–T4), code-search 2 skills + references + check-tools (T5–T8), stubs
  unlisted (T9–T10), CI/pre-commit/best-practices (T11), `/init` contributor
  guide (T12), final validation incl. dependency + catalog assertions (T13). All
  spec sections mapped.
- **Open questions** (RAG corpus, Obsidian scope, embedding defaults) are
  intentionally deferred to those plugins' future specs; stubs say so explicitly.
- **Type/name consistency:** plugin names (`retrieval-core`, `code-search`,
  `local-rag`, `obsidian`), skill names, agent name `retrieval-strategist`, and
  `dependencies: ["retrieval-core"]` are used identically across tasks.
- **Known external unknowns flagged for execution:** the CI global CLI package
  name (T11); confirm `claude plugin validate --strict` tolerates stubs whose
  only skill is a placeholder (T9–T10).
```
