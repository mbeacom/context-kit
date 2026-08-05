---
name: token-accounting
description: "Use when measuring or reporting agent token usage, cost, or cache efficiency from Claude Code or GitHub Copilot session records."
license: MIT
compatibility: "Reads local host files only. Requires Python 3 and, for the Copilot host, a readable SQLite session store. Neither host guarantees these formats; the reader degrades to a disclosed gap rather than a wrong number."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash
---

# Token Accounting

Report what an agent actually spent, from the host's own records, without
inflating the number.

Token totals look like simple sums. They are not. Each host stores usage in a
shape whose obvious reading is wrong, and both errors are large enough to change
a decision. Get the arithmetic right before reporting anything.

## The three traps

Every number this skill produces exists because a naive total gets these wrong.

**1. Replayed records (Claude Code).** Transcripts under `~/.claude/projects`
append one line per API response, but resumed sessions, sidechains, and subagent
transcripts replay the same response. Deduplicate on
`(requestId, message.id)` — both, since one request can stream several messages
and the same message is copied into subagent files. On a real developer machine
this removed 60% of records and cut the token total by more than half.

**2. Inverted cache semantics.** The two hosts mean opposite things by the same
field name:

| Host | `input_tokens` | Billable uncached input |
| --- | --- | --- |
| Claude Code | excludes cache | the field as written |
| GitHub Copilot CLI | includes cache | `input_tokens − cache_read − cache_write` |

Pricing Copilot's raw column at the input rate overstated real uncached input by
roughly 950× on live data. Never price a column whose semantics you have not
confirmed.

**3. Token class is not token cost.** Cache reads dominate volume — around 97% of
input-side tokens on both hosts — and bill at roughly a tenth of the input rate,
while cache writes bill at a premium and output costs several times input. A
total token count therefore says little about spend. Report classes separately
and quote the cache hit ratio.

## Collect

```bash
ROOT="${CONTEXT_KIT_TOKEN_ECONOMICS_ROOT:-$CLAUDE_PLUGIN_ROOT}"
python3 "$ROOT/scripts/collect_usage.py" --host claude --host copilot
python3 "$ROOT/scripts/collect_usage.py" --format json
```

Inside Claude Code plugin components, use
`${CLAUDE_PLUGIN_ROOT}/scripts/collect_usage.py` when the neutral plugin root
variable is not available. Prefer `CONTEXT_KIT_*` variables in portable
instructions.

Override source discovery with `CONTEXT_KIT_CLAUDE_PROJECTS` and
`CONTEXT_KIT_COPILOT_DB`. The reader opens SQLite read-only and never writes.

Exit `1` means no records were found on any requested host — an absent source,
not zero usage. Say so rather than reporting a zero.

## Grade every number

Attach both grades whenever you report a figure, and keep them attached
downstream:

- **Counting** — `exact` when the host recorded the count; `estimated` when it
  came from a heuristic.
- **Attribution** — telemetry is always `observational`. It shows what happened,
  never what caused it.

That second grade is the one people drop. Usage falling after adopting a tool
does not show the tool caused it; the work changed too. To claim a tool saved
tokens, run a controlled comparison — see the `tool-savings-benchmark` skill.
Route any savings figure that will be quoted to someone else through
`verify-before-trust`.

## Cost

Report cost only in the unit the host actually recorded.

- **Copilot CLI** records `total_nano_aiu` per request and its own per-model rate
  card in `token_details_json`, so cost is exact and needs no price table.
  Premium-request multipliers bill separately; do not fold them in.
- **Claude Code** records no cost. Tokens are exact; any currency figure is your
  own price assumption and must be labelled as one. On a subscription plan the
  marginal cost of a token is zero, so a dollar saving there is fiction — report
  tokens and context headroom instead.

## References

- `references/host-data-sources.md` — exact schemas, field semantics, stability.
- `references/fleet-telemetry.md` — OpenTelemetry and org-level rollups.
- `references/reporting.md` — what a defensible report states and omits.
