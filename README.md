# productivity-skills

A [Claude Code](https://code.claude.com) plugin **marketplace** for information
retrieval. It bundles complementary **retrieval modalities** — lexical,
structural, structured-data, history, semantic (RAG), and graph — plus a routing
agent that picks and composes them. Everything runs **locally**; the RAG layer
keeps your corpus on your machine.

## Install

```bash
/plugin marketplace add mbeacom/productivity-skills
```

Then install what you need (installing `code-search` auto-installs `retrieval-core`):

```bash
/plugin install code-search@productivity-skills     # lexical/structural/data/history search
/plugin install local-rag@productivity-skills        # local semantic search (turbovec + ollama)
/plugin install obsidian@productivity-skills          # Obsidian vault → RAG bridge
```

## Plugins

| Plugin | What it does |
| --- | --- |
| **retrieval-core** | The spine: a `retrieval-strategist` agent + `retrieval-strategy` skill that choose and compose modalities. Other plugins depend on it. |
| **code-search** | Lexical (`rg`/`fd`), structural (`ast-grep`/`semgrep`), structured-data (`jq`/`yq`/`gron`), history (`git` pickaxe/`difftastic`), structured rewrite (`comby`), metrics (`tokei`/`scc`), and non-code docs (`rga`/`pandoc`/`pdftotext`). Two skills: `code-search` (code) and `data-and-docs-search` (data/docs). |
| **local-rag** | Fully-local semantic search: a `bin/rag` CLI that chunks a corpus, embeds it with **ollama**, and indexes it with **turbovec**. Notes-first, corpus-agnostic, with incremental indexing and hybrid `--allowlist` retrieval. |
| **obsidian** | A skill-only **RAG bridge**: turn an Obsidian vault's graph/tags (official `obsidian` CLI, or `rg` fallback) into a candidate set fed to `local-rag`. For authoring/Bases/Canvas, use [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills). |

## Requirements

The skills degrade gracefully and tell you what's missing.

- **code-search** — needs `rg` (ripgrep); the rest are optional. Run
  `bash plugins/code-search/scripts/check-tools.sh` to see what's installed and
  the `brew install …` line for the rest.
- **local-rag** — needs [`uv`](https://docs.astral.sh/uv/) (the `rag` CLI is
  bootstrapped into a venv automatically on session start) and a running
  [ollama](https://ollama.com) with an embedding model:
  `ollama serve` + `ollama pull nomic-embed-text`.
- **obsidian** — optional: the official `obsidian` CLI (with Obsidian running)
  for graph-accurate queries; otherwise falls back to `rg`/`fd`. Set your vault
  path in the plugin's config (`vault_path`).

## Usage

Once installed, Claude invokes the skills automatically based on your task. The
**`retrieval-strategist`** agent (or the `retrieval-strategy` skill) decides which
modality fits — and they **compose**.

**Pick a modality by what you know:**

| You know… | Modality | Example |
| --- | --- | --- |
| an exact token / regex / filename | lexical | `rg -t py 'def login'` · `fd -e ts` |
| the code *shape*, not the text | structural | `sg -p 'logger.debug($$$)' --lang js` |
| a JSON/YAML schema path | structured-data | `jq '.scripts' package.json` · `gron x.json \| rg token` |
| *when/why* code changed | history | `git log -S'retry' -- src/` |
| only the *meaning/intent* | semantic (RAG) | `rag query "how do we handle backoff" --name notes` |
| the corpus is an Obsidian vault | graph | `obsidian backlinks file="Project X"` |

**Semantic search (local-rag):**

```bash
ollama pull nomic-embed-text                 # once
rag index /path/to/vault --name notes        # build/update (incremental)
rag query "open questions about billing" --name notes --k 8
rag status --name notes                       # counts, model, dim, staleness
```

**Hybrid retrieval (the payoff) — narrow with the graph/lexical, rerank with vectors:**

```bash
# Obsidian graph → semantic rerank (official CLI)
obsidian backlinks file="Project X" | rag query "open risks" --name notes --allowlist -

# rg fallback when Obsidian isn't running
rg -l '#decision' "$VAULT" | rag query "why did we choose X" --name notes --allowlist -
```

`rag` returns `path > heading` + a snippet; follow up with `rg` to pin exact lines.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the modality model and how the
plugins fit together.

## Development

```bash
# Validate the marketplace + every plugin
claude plugin validate . --strict
for p in plugins/*/; do claude plugin validate "$p" --strict; done

# Lint (markdownlint + shellcheck + ruff + hygiene)
pre-commit run --all-files

# Run the local-rag Python tests
cd plugins/local-rag && uv run --group dev pytest -q
```

See [CLAUDE.md](CLAUDE.md) for contributor conventions.

## License

MIT © Mark Beacom. Each plugin ships its own `LICENSE`.
