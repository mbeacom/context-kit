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
