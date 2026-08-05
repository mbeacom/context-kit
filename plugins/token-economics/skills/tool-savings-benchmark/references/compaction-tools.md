# Compaction tools

Tools that shrink what an agent reads. All are optional; none is required by this
plugin, and the correct choice is frequently a flag you already have.

Measure before adopting. Every entry below advertises a percentage measured on
someone else's corpus.

## Native flags first

The cheapest compaction is usually already installed, adds no dependency, and
cannot silently drop information because you chose what to omit:

| Instead of | Use | Why |
| --- | --- | --- |
| `rg pattern` | `rg -c pattern` | counts per file, not matching lines |
| `rg pattern` | `rg -l pattern` | paths only, when you will read them next |
| `git diff` | `git diff --stat` | shape of the change before the content |
| `git log` | `git log --oneline -n 20` | bounded by construction |
| `jq .` | `jq -c` / narrow path | avoids pretty-printing an entire document |
| `cat file` | ranged read | reads the region, not the file |

Benchmark a wrapper against the best native flag, not against the naive command.
A wrapper that beats `cat` but loses to `rg -c` has not earned an install.

## `rtk` (Rust Token Killer)

<https://github.com/rtk-ai/rtk> — a proxy that compacts output from a known set
of dev commands. Prefixing is safe on any command: unwrapped ones pass through.
It only *saves* on the wrapped set, so prefixing elsewhere is noise.

`code-search` already documents rtk in detail, including which tools it wraps and
the pipe-safety rules. Read
`plugins/code-search/skills/code-search/references/rtk.md` before wiring it into
a pipeline.

Benchmark note: rtk reformats output, so a run whose assertion depends on exact
formatting will fail against it. Assert on the *answer* (a symbol, a path, a
count), not on layout.

## `headroom`

<https://github.com/headroomlabs-ai/headroom> — Apache-2.0, Python and
TypeScript. Compresses tool outputs, logs, files, and RAG chunks before they
reach the model. Ships as a library, a proxy (`headroom proxy`), an MCP server,
and an agent wrapper (`headroom wrap claude`, `headroom wrap copilot`), so it can
sit in front of either host this plugin reads.

Advertised: 15–20% fewer tokens for coding agents, 60–95% for JSON. The gap
between those figures is the important part — compaction pays most on verbose
structured data and least on output that is already terse. Which regime your
commands fall into is exactly what a benchmark decides.

It exposes a `headroom_stats` MCP tool. Treat its self-reported savings as
`observational` and vendor-defined: it reports what it compressed, which is not
the same as what a task would have cost without it. For a quotable number, run
the controlled comparison.

Because it is reversible and content-aware rather than a truncator, the
preserved-answer assertion matters more, not less — verify the specific fact your
task needs still survives.

## Choosing between them

They are not exclusive: rtk compacts a fixed set of dev-command formats, while
headroom compresses arbitrary payloads including JSON and logs. Stacking them is
possible but makes attribution harder — benchmark each arm separately before
combining, or you will not know which one earned the saving.

Prefer the smallest intervention that survives measurement:

1. A native flag, if one answers the question.
2. A single wrapper, benchmarked on your real commands.
3. A proxy layer, only when many command shapes need it.

## Cost of adoption

A compaction layer is a dependency in the path of everything the agent reads. It
can fail, lag, change format between versions, or drop the one line that
mattered. That cost is real and does not appear in a token count — weigh it
against a saving that must be material to be worth taking at all.
