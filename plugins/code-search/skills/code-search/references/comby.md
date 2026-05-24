# comby

Structural search-and-replace that understands balanced delimiters (parens,
brackets, braces, strings) across many languages — without a full grammar per
language. Great for lightweight, multi-language rewrites.

## Hole syntax

`:[name]` is a *hole* that matches a balanced span and binds it to a name you can
reuse in the rewrite. Variants: `:[[name]]` (alphanumeric only), `:[name~regex]`
(constrained), `:[ ]` (whitespace).

## Match (default is dry-run — nothing is written)

```bash
comby 'logger.debug(:[args])' '' -matcher .js .   # find debug-log calls
comby 'if (:[c]) { :[body] }' '' .ts              # all single-branch ifs
```

The second argument is the rewrite template; an empty `''` means "match only".

## Rewrite

```bash
comby 'foo(:[x])' 'bar(:[x])' .py                 # preview the diff
comby 'foo(:[x])' 'bar(:[x])' .py -i              # -i writes IN PLACE
```

## Scope: directories, matchers, language extensions

```bash
comby 'logger.debug(:[a])' 'logger.info(:[a])' .js -d src/   # restrict to a dir
comby 'pattern' 'rewrite' -matcher .go                       # pick the matcher
comby 'pattern' 'rewrite' .ts .tsx                           # several extensions
```

`.lang`-style arguments (e.g. `.js`, `.go`, `.py`) both filter files and select
the matcher. Without `-i`, comby only prints a unified diff — review first.

## When to choose comby over `sg`

- The change spans **multiple languages** with one template, or a language
  `sg` has no grammar for.
- You want **lighter syntax** (holes, balanced-delimiter matching) without
  writing AST patterns.
- The edit is delimiter-shaped (wrap/unwrap args, swap call names) rather than
  deeply structural.

Prefer **`sg --rewrite`** (ast-grep) when you need AST-precise edits — true
syntax nodes, type-aware constraints, and guaranteed structural correctness.
