# productivity-skills

A [Claude Code](https://code.claude.com) plugin **marketplace** for
information retrieval: search modalities, a routing agent, and (soon) local RAG
and Obsidian support.

## Install

```bash
/plugin marketplace add mbeacom/productivity-skills
/plugin install code-search@productivity-skills
```

`code-search` pulls in `retrieval-core` automatically.

## Plugins

- **retrieval-core** — a retrieval-strategist agent + decision-flow skill that
  picks and composes search modalities.
- **code-search** — lexical (`rg`/`fd`), structural (`ast-grep`/`semgrep`),
  structured-data (`jq`/`yq`/`gron`), history (`git` pickaxe), structured
  rewrite (`comby`), data files (`duckdb`), metrics (`tokei`/`scc`), and
  non-code docs (`rga`).
- **local-rag** *(planned)* — `turbovec` + `ollama` local semantic search.
- **obsidian** *(planned)* — vault conventions + link-graph retrieval.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT © Mark Beacom. Each plugin ships its own `LICENSE`.
