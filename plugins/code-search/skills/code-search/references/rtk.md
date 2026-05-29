# rtk — optional token-saving CLI wrapper

[`rtk`](https://github.com/rtk-ai/rtk) (Rust Token Killer) is a CLI proxy that
compacts common dev-command output by 60–90%. It is **optional**: if it is not
installed, run every tool directly — nothing here is required.

## When to use it

If `command -v rtk` succeeds, prefix the **rtk-wrapped** tools below; rtk
compacts their output. Prefixing is always safe (an unwrapped command passes
through unchanged), but it only *saves tokens* on the wrapped set — so there's no
reason to prefix the rest.

Some users run an rtk hook that auto-rewrites Bash commands; don't rely on it —
write the `rtk`-prefixed form explicitly so the skill works without the hook.

## What rtk wraps

| Tool          | Prefixed form                        |
| ------------- | ------------------------------------ |
| `rg` / `grep` | `rtk rg …`, `rtk grep …`             |
| `git`         | `rtk git log …`, `rtk git diff …`    |
| `find`        | `rtk find …`                         |
| `diff`        | `rtk diff …`                         |

In these skills you'll prefix `rg` (and `git` in code-search): `rtk rg …`,
`rtk git log …`, `rtk git diff …`. `grep`/`find`/standalone `diff` are
rtk-wrapped too, but these skills prefer `rg`/`fd`/`git`, so you won't usually
prefix them here — which is why their scoped `allowed-tools` list only `rtk rg`
and `rtk git`.

**Not wrapped — run directly** (rtk would only pass them through): `fd`, `sg`
(ast-grep), `semgrep`, `comby`, `difft`, `tokei`, `scc`, `jq`, `yq`, `gron`,
`duckdb`, `sqlite-utils`, `rga`, `pandoc`, `pdftotext`. Keep `fd` for file
finding (faster, gitignore-aware) rather than rtk's `find`.

## Pipes: don't let compaction corrupt piped data

rtk *reformats* a wrapped tool's output, which can break a downstream program
that parses it. Two safe rules:

- rtk's grep/rg filter passes the format flags `-c -l -L -o -Z` through **raw**,
  so `rtk rg -c …` (count) and `rtk rg -l …` (paths) are pipe-safe — including
  `rtk rg -l … | rag query --allowlist -`.
- For any other wrapped tool feeding another program, use the bare CLI or
  `rtk proxy <cmd>` (forces raw output). Prefix `rtk` freely on the final stage
  whose output you read.
