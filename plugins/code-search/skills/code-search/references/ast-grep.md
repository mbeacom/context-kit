# ast-grep (`sg`)

Syntax-aware (AST) search and rewrite. Patterns are written as *code*, so
whitespace, formatting, and comments don't matter — only structure does. Prefer
`sg` over `rg` when you need to match language constructs (calls, defs, imports)
rather than raw text.

## Pattern metavariables

- `$VAR` matches a single named node (e.g. one argument, one identifier).
- `$$$` matches zero or more nodes (variadic) — e.g. an argument list.
- `$$$ARGS` captures the variadic match for reuse in a rewrite.
- `--lang` (or `-l`) selects the grammar; required when it can't be inferred.

## Search

```bash
sg -p 'logger.debug($$$)' --lang js          # any debug-log call
sg -p 'await $X.$METHOD($$$)' --lang ts       # any awaited method call
sg -p 'if ($C) { $$$ }' --lang go             # all single-branch ifs
```

## Rewrite

```bash
sg -p 'logger.debug($$$A)' -r 'logger.info($$$A)' --lang js
sg -p 'console.log($MSG)' -r 'logger.debug($MSG)' --lang ts --update-all
```

By default `sg` prints a diff; pass `--update-all` (or `-U`) to apply edits.

## YAML rules and relational constraints

For reusable, shareable rules use `sg scan`:

```bash
sg scan -r rule.yml             # run a single rule file
sg scan                          # run sgconfig.yml across the project
```

```yaml
# rule.yml — flag a debug log that sits inside a loop
id: debug-log-in-loop
language: js
rule:
  pattern: logger.debug($$$)
  inside:
    kind: for_statement
```

Relational keys: `inside`, `has`, `precedes`, `follows` let you constrain a match
by its surrounding structure (e.g. a call that `has` a specific argument).

## When to prefer `sg` over `rg`

- The thing you want is a code construct (a function definition, an import, a
  specific call shape), not a literal string.
- You want formatting-insensitive matches (multi-line calls, reordered spaces).
- You intend to rewrite structurally and want balanced-delimiter safety.

Use `rg` when the target is plain text/comments or when no grammar exists.

## Per-language examples

```bash
sg -p 'def $NAME($$$): $$$' --lang python     # every function definition
sg -p 'import $WHAT from "$MOD"' --lang ts     # ES module imports
sg -p 'func $NAME($$$) $RET { $$$ }' --lang go # Go function decls
sg -p 'fn $NAME($$$) -> $RET { $$$ }' --lang rust  # Rust fns with return type
```
