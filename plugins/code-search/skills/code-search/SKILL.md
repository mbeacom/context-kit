---
name: code-search
description: "Use when searching source code: text/regex (ripgrep), structural/AST patterns (ast-grep, semgrep), symbol definitions/references/call hierarchy (LSP, GNU Global, ctags), when/why code changed (git history), structural rewrites (comby), or codebase size/complexity (tokei, scc)."
license: MIT
compatibility: "Requires ripgrep (rg). Optional: fd, ast-grep (sg), semgrep, comby, difftastic, tokei, scc, GNU Global (global), universal-ctags (ctags), and rtk (rtk-ai/rtk) for compact rg/git output."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Bash(rg:*) Bash(fd:*) Bash(sg:*) Bash(ast-grep:*) Bash(semgrep:*) Bash(git:*) Bash(comby:*) Bash(difft:*) Bash(tokei:*) Bash(scc:*) Bash(global:*) Bash(gtags:*) Bash(ctags:*) Bash(readtags:*) Bash(rtk rg:*) Bash(rtk git:*) Read Glob Grep
---

# Code Search

CLI search for source code. Pick the modality by what you know.

This skill is portable across GitHub Copilot, APM, and Claude Code; keep the
`references/` folder next to `SKILL.md` when copying it into a Copilot skill
location.

| Task                              | Use                  | Reference                       |
| --------------------------------- | -------------------- | ------------------------------- |
| Text / regex in code              | `rg`                 | [ripgrep](references/ripgrep.md) |
| Find files by name/path           | `fd`                 | [fd](references/fd.md)           |
| Structural / syntax-aware search  | `sg` (ast-grep)      | [ast-grep](references/ast-grep.md) |
| Security/lint rule packs, taint   | `semgrep`            | [semgrep](references/semgrep.md) |
| Symbol defs / refs / call hierarchy | LSP · `global` · `ctags` | [code-intelligence](references/code-intelligence.md) |
| When/why code changed             | `git log -S/-G/-L`   | [git-history](references/git-history.md) |
| Structural search-and-replace     | `comby`, `sg --rewrite` | [comby](references/comby.md)  |
| Size / complexity by language     | `tokei`, `scc`       | [metrics](references/metrics.md) |

**Decision flow:** text → `rg` | structural → `sg` | symbol defs/refs → LSP/`global` |
rule packs → `semgrep` | filenames → `fd` | change history → `git` pickaxe |
rewrite → `comby` | LOC → `tokei`.

## Best practices

1. **Start narrow** — scope by type (`rg -t py`, `sg --lang ts`, `fd -e go`),
   restrict dirs, and **count first** (`rg -c pattern | wc -l`) before reading.
2. **Exclude noise** — `rg -g '!vendor/' -g '!*.lock'`, `fd -E node_modules`.
3. **Batch independent queries** — union patterns (`rg -e P1 -e P2`) in one walk,
   or issue distinct searches as parallel tool calls. Never sequential `&&`.
4. **`rg -t ts` includes `.tsx`; `fd -e ts` does NOT** — use `fd -e ts -e tsx`.
5. For cross-modality strategy (semantic/graph, hybrid rerank), see the
   `retrieval-strategy` skill or invoke the `retrieval-strategist` agent.
6. **Prefer `rtk` when installed** — prefix the rtk-wrapped tools (`rtk rg …`,
   `rtk git log …`) for 60–90% smaller output; other tools run directly and
   `rtk rg -c`/`-l` stay raw (pipe-safe). See [rtk](references/rtk.md).

For non-code corpora (JSON/YAML, CSV/Parquet, PDFs/Office), use the
`data-and-docs-search` skill.
