# code metrics (`tokei`, `scc`)

Fast counters for codebase size and complexity by language. Both walk the tree,
respect `.gitignore`, and far outpace `cloc` or `wc -l`.

## tokei — fast lines-of-code

```bash
tokei                           # LOC table: code / comments / blanks by language
tokei --sort code               # sort languages by code lines (desc)
tokei -o json                   # machine-readable output (also yaml, toml)
tokei src/ tests/               # restrict to specific paths
tokei -e vendor/ -e dist/       # exclude paths
```

Use `tokei` when you just need accurate, instant LOC totals.

## scc — LOC plus complexity and cost

```bash
scc                             # LOC + cyclomatic complexity per language
scc --wide                      # adds complexity/byte and COCOMO cost estimate
scc --by-file                   # per-file breakdown (find the heaviest files)
scc -f json                     # JSON output
scc --no-cocomo                 # skip the cost model if you only want complexity
```

Use `scc` when you care about **complexity hotspots** or want a rough **cost /
effort** estimate, not just line counts.

## Which to use

| Need                              | Tool   |
| --------------------------------- | ------ |
| Fastest raw LOC totals            | `tokei` |
| Cyclomatic complexity per file    | `scc`   |
| COCOMO cost / effort estimate     | `scc --wide` |
| JSON for a dashboard or CI badge  | either (`-o json` / `-f json`) |

Both are dramatically faster and more accurate than `cloc`, and far more
informative than `find ... | xargs wc -l`, which miscounts comments/blanks and
ignores language structure.
