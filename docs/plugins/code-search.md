# code-search

!!! abstract "Fast CLI search across modalities"
    Lexical, structural, code-intelligence, structured-data, history, structured
    rewrite, metrics, and non-code document search — packaged as two skills split
    by corpus.

`code-search` gives an agent modern, fast command-line search for source code and
for data/documents. It declares `dependencies: ["retrieval-core"]`, so installing
it also lands the [retrieval spine](retrieval-core.md).

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install code-search@context-kit   # auto-installs retrieval-core
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install code-search@context-kit   # also pulls retrieval-core
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install code-search@context-kit   # auto-installs retrieval-core
    ```

## Skills

| Skill | Modalities | Tools |
| --- | --- | --- |
| **`code-search`** | lexical, structural, code-intelligence, history, structured rewrite, metrics | `rg`, `fd`, `ast-grep`/`sg`, `semgrep`, `global`, `ctags`, `git log -S/-G/-L`, `difftastic`, `comby`, `tokei`, `scc` |
| **`data-and-docs-search`** | structured-data, data files, non-code docs | `jq`, `yq`, `gron`, `duckdb`, `sqlite-utils`, `rga`, `pandoc`, `pdftotext` |

## Examples

```bash
# Lexical: exact token / filename
rg -t py 'def login'
fd -e ts --changed-within 2d

# Structural: match code shape, not text
sg -p 'logger.debug($$$)' --lang js

# History: when/why a string appeared or vanished
git log -S'retry_backoff' -- src/

# Structured-data: query a schema path
jq '.scripts' package.json
gron config.json | rg 'timeout'
```

## Requirements

Only `rg` (ripgrep) is required; everything else is optional and the skills
degrade gracefully, telling you what's missing. From a clone of the repo, the
bundled checker reports what's installed and the `brew install …` line for the rest:

```bash
bash plugins/code-search/scripts/check-tools.sh
```

!!! note "rtk and pipes"
    `rtk` (Rust Token Killer) compacts command output for lower token use, but it
    *reformats* wrapped output — which can corrupt data piped into another program.
    Use raw-preserving flags (`-c`/`-l`) or `rtk proxy <cmd>` for intermediate pipe
    stages. See the plugin's `references/rtk.md`.

## At a glance

| | |
| --- | --- |
| **Category** | retrieval |
| **Provides** | 2 skills, a tool checker script |
| **Dependencies** | [`retrieval-core`](retrieval-core.md) |
| **Required tool** | `rg` (ripgrep) |
| **License** | MIT |
