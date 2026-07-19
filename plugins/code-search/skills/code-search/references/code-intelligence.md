# code intelligence (symbol defs / refs / call hierarchy)

Symbol-aware navigation resolves a *symbol* to its binding — the true
definition, every reference/caller, the call hierarchy, implementations — using
a language-aware index, not text or syntax shape. Reach for it when you know the
symbol and want where it is **defined** or **used**, resolved across files.

## When this beats `rg` / `sg`

- `rg` matches **text**: it misses aliases and re-exports, and over-matches a
  common name shared by unrelated symbols.
- `sg` (ast-grep) matches **syntactic shape** within one language, but does not
  resolve a name to its declaration or find semantic references project-wide.
- Code intelligence resolves the **binding**: "the `parseConfig` defined in
  `config.ts`, and its 12 real callers" — not every line containing that word.

## Prefer host-provided code intelligence / LSP first

Copilot and Claude expose go-to-definition, find-references, and symbol tools
backed by a language server. These are the most accurate (type-aware); use them
before shelling out. Only fall back to the CLIs below when no such tool is
available.

## GNU Global — definitions AND references

```bash
gtags                       # build the index once at the repo root
global -x  parseConfig      # definitions, with file:line
global -xr parseConfig      # references / callers
global -xs MAX_RETRIES      # symbol uses that are not definitions
global -c  parse            # completion: symbols with this prefix
```

`global` is the strongest portable CLI for **references**. Re-run `gtags`
(or `global -u`) after edits to refresh the index.

## universal-ctags — definitions

```bash
ctags -R --fields=+n .              # build a tags DB with line numbers
readtags -t tags -en - UserService  # query a symbol's definition(s)
```

`ctags` indexes **definitions** (tags) well; it is not a reference finder. Pair
it with `global` (or `rg`) for callers. Note: system/BSD `ctags` lacks
`readtags` and `--fields`; install universal-ctags for the query commands.

## Large monorepos — SCIP / LSIF

For repo-scale cross-references, a precomputed SCIP/LSIF index (built by a
language-specific indexer such as `scip-typescript index` or `scip-python
index`) scales better than re-running `gtags`. Overkill for a single package.

## Compose with the other modalities

```bash
# Resolve then pin: get the real callers, then expand exact lines with context.
global -xr parseConfig | awk '{print $3}' | sort -u \
  | xargs -I{} rg -n -C2 'parseConfig' {}

# Shape then resolve: ast-grep finds a call shape; code intelligence confirms the
# real binding and dedupes text-only overmatches.
sg -p 'parseConfig($$$)' --lang ts      # candidate call sites, by syntax shape
global -xr parseConfig                  # the resolved references to compare against
```

## Degrade gracefully

If no host LSP, `global`, or universal-`ctags` is available, say so and fall
back to a word-boundary text search — then warn that it can miss aliases and
over-match:

```bash
rg -nw 'parseConfig'        # -w = whole word; closest text approximation
```

Suggest the install (`brew install global universal-ctags`) rather than
pretending a semantic index exists.
