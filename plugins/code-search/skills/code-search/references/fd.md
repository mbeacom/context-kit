# fd

A fast, user-friendly file finder. Respects `.gitignore` by default and matches
on file *names/paths*, not contents. Use it to locate files before searching
inside them.

## Match by name, glob, extension

```bash
fd foo                          # substring match on the filename
fd '^test_' -e py               # regex name match, Python only
fd -g '*.test.ts'               # glob mode (instead of regex)
fd -e ts -e tsx                 # one or more extensions
```

## Filter by type, hidden, ignore, depth

```bash
fd -t f config                  # files only
fd -t d migrations              # directories only
fd -t l                         # symlinks only
fd -H secret                    # include hidden (dot) files
fd -I dist                      # do NOT respect .gitignore
fd -d 2 readme                  # limit recursion depth to 2
```

## Filter by modification time

```bash
fd --changed-within 1d          # touched in the last day
fd --changed-within 2weeks -e log
fd --changed-before 2024-01-01  # older than a date
```

## Run a command on the results

```bash
fd -e go -X rg 'func Test'      # one rg invocation over ALL matched files
fd -e py -x wc -l               # run wc -l once PER file
fd -e json -x jq . {}           # {} is the placeholder for each path
```

## Exclude paths and match full path

```bash
fd -E node_modules -E dist 'index'      # prune directories
fd -p 'src/.*/handlers/.*\.ts'          # -p matches the full path, not just name
```

## Gotcha: `rg -t` vs `fd -e`

`rg -t ts` includes both `.ts` **and** `.tsx` (the `ts` type covers both).
`fd -e ts` matches **only** `.ts`. To cover TSX with `fd`, list both:

```bash
fd -e ts -e tsx                 # equivalent coverage to `rg -t ts`
```
