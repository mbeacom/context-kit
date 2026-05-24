# jq · yq · gron

Query and reshape structured config. Use `jq` for JSON when you know the path,
`gron` when you don't, and `yq` for YAML/TOML/XML.

## jq — JSON

```bash
jq '.a.b' config.json               # nested field access
jq '.items[]' data.json             # iterate an array
jq '.items[0]' data.json            # index a single element
jq '.items[] | select(.qty > 1)'    # filter by predicate
jq 'keys' object.json               # list keys of an object
jq -r '.name' data.json             # -r: raw output (no quotes) for shell use
jq -c '.items[]' data.json          # -c: one compact JSON object per line
jq 'to_entries[] | {k:.key, v:.value}'   # turn an object into k/v rows
jq -c 'paths(scalars)' data.json    # enumerate every leaf path
```

Find every value under a key named `id`, no matter how deep:

```bash
jq -c '.. | objects | select(has("id")) | .id' data.json
```

## gron — make JSON greppable

`gron` flattens JSON into assignment lines you can `rg` over — perfect when the
path is unknown or deeply nested.

```bash
gron data.json | rg 'token'                 # find any path mentioning 'token'
gron data.json | rg '\.items\[\d+\]\.id'    # grep structural paths directly
gron data.json | rg 'enabled = true'        # find where a flag is set
gron data.json | rg 'token' | gron -u       # -u rebuilds JSON from the matches
```

Why it beats `jq` when the path is unknown: you get line-oriented, fully-qualified
paths that ripgrep's regex, context, and counting features apply to directly — no
need to guess the shape first.

## yq — YAML / TOML / XML (mikefarah yq)

```bash
yq '.a.b' file.yaml                 # field access (jq-like syntax)
yq '.services | keys' compose.yaml  # keys of a mapping
yq -p toml '.tool.name' pyproj.toml # parse TOML input (-p)
yq -p xml '.root.child' file.xml    # parse XML input
yq -o json '.' file.yaml            # convert YAML -> JSON (-o output format)
yq -o toml '.' file.yaml            # convert to TOML
yq ea '[.]' multi.yaml              # eval-all: fold a multi-document stream
```

Note: this is the **mikefarah** `yq` (Go). The unrelated Python `yq` is a jq
wrapper with different invocation — flags here assume mikefarah.
