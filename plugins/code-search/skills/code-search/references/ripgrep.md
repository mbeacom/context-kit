# ripgrep (`rg`)

Fast recursive regex search. Respects `.gitignore` by default. Use it as the
first tool for any plain-text or regex lookup.

## Scope by file type

```bash
rg -t py 'def handler'          # only Python files
rg -T test 'TODO'               # exclude the 'test' type
rg --type-list                  # show all known types and their globs
```

## Case, word, and literal matching

```bash
rg -i 'connect'                 # case-insensitive
rg -S 'Connect'                 # smart-case: literal unless pattern has uppercase
rg -w 'id'                      # whole word only (not 'uuid', 'idx')
rg -F 'a.b.c'                   # fixed string, no regex metacharacters
```

## Count first, then drill in

```bash
rg -c 'logger.debug' src/       # per-file match counts — cheap triage
rg -c 'logger.debug' | wc -l    # how many files match at all
rg -A2 -B2 'logger.debug' app/  # then read with context
```

## Context, file lists, only-matching

```bash
rg -A 3 'requests.get'          # 3 lines After
rg -B 3 'requests.get'          # 3 lines Before
rg -C 3 'requests.get'          # 3 lines around (context)
rg -l 'requests.get'            # files-with-matches (names only)
rg -o 'v\d+\.\d+\.\d+'          # print only the matched substring
```

## Multiline and PCRE2

```bash
rg -U 'try\s*\{[\s\S]*?\}'                 # multiline mode
rg -U --multiline-dotall 'start.*end'      # '.' also spans newlines
rg -P '(?<=\bclass )\w+'                   # PCRE2 lookbehind/lookahead
```

## Globs, hidden files, and ignore rules

```bash
rg -g '!vendor/' -g '!*.lock' 'TODO'       # exclude paths/globs
rg -g '*.{ts,tsx}' 'useEffect'             # brace expansion in globs
rg --hidden 'pattern'                       # include dotfiles
rg -u 'pattern'                             # one -u: don't respect .gitignore
rg -uu 'pattern'                            # also search hidden files
```

## Union patterns, replace preview, JSON

```bash
rg -e 'requests.get' -e 'requests.post'    # OR several patterns in one walk
rg 'foo' -r 'bar'                          # preview a replacement (no write)
rg --json 'pattern' | jq -c 'select(.type=="match")'
```

## Recipe: find committed credentials

Search for assignment-style secrets generically — match a key name followed by
`=` and a quoted value, without embedding any real secret:

```bash
rg -n -i -e '(api[_-]?key|token|secret|password)\s*[:=]\s*["'"'"'][^"'"'"']{8,}'
```

Pair with `-g '!*.lock'` and `--hidden` to catch `.env`-style files.

## Recipe: TODO / FIXME census

```bash
rg -n -e 'TODO' -e 'FIXME' -e 'XXX' -e 'HACK' --stats
rg -o -e 'TODO' -e 'FIXME' | sort | uniq -c | sort -rn   # counts per tag
```
