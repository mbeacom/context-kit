# token-economics

Measure agent token usage, and prove a tool's savings instead of repeating the
percentage on its README.

The catalog recommends tools that claim to reduce tokens. This plugin is how
those claims get checked — and how a usage report survives someone reading it
closely.

## Why it exists

Token totals look like simple sums. Measured on a live developer machine:

- **60.4%** of Claude Code usage records are replayed responses. Summing them
  overstates tokens by **132.6%**.
- Copilot's `input_tokens` column **includes** cache traffic while Claude Code's
  **excludes** it. Pricing the raw column overstated uncached input by ~**950×**.
- **~97%** of input-side tokens are cache reads, billed at roughly a tenth of the
  input rate — so a token total says little about spend.

And the claim people actually want — "this tool saved us money" — cannot be
answered by any of that data, because telemetry cannot attribute a change to a
cause. That needs a controlled comparison.

## Skills

| Skill | Use when |
| --- | --- |
| `token-accounting` | Measuring or reporting usage, cost, or cache efficiency. |
| `tool-savings-benchmark` | Claiming or testing that something reduces tokens. |

## Commands

- `/token-report [claude\|copilot\|both]` — usage from local host records.
- `/benchmark-tool-savings <claim>` — controlled A/B for a savings claim.

## Scripts

Both are standard-library Python 3 with no dependencies, and read-only with
respect to host data.

```bash
# Usage totals, deduplicated, with cache decomposition per host.
python3 plugins/token-economics/scripts/collect_usage.py --format json

# Does rtk actually beat plain rg on this repo?
python3 plugins/token-economics/scripts/benchmark_savings.py \
  --baseline "rg -n 'func handleAuth' ." \
  --candidate "rtk rg -n 'func handleAuth' ." \
  --must-contain "handleAuth"
```

`collect_usage.py` exits `1` when no records exist — an absent source, not zero
usage. `benchmark_savings.py` exits `1` for an `unverified` verdict and `2` for a
setup error.

## The rule worth knowing

**A savings number means nothing without evidence the answer survived.**

Discarding output entirely "saves" 100%. Any comparison measuring only output
size ranks the most destructive tool first. So every benchmark declares what the
output must still contain, and a run without that assertion cannot produce a
quotable result.

Every figure carries two grades: **counting** (`exact` or `estimated`) and
**attribution** (`controlled` or `observational`). Session telemetry is always
observational, however precise the count.

## Hosts

Claude Code and GitHub Copilot CLI, read from their local records. The two stores
have opposite cache semantics, which the collector handles per host. Fleet
rollups are covered in
`skills/token-accounting/references/fleet-telemetry.md` — Claude Code exports
OpenTelemetry; Copilot CLI exports no token data, and its organization APIs
report engagement only.

Nothing here sends data anywhere.

## Configuration

| Variable | Default |
| --- | --- |
| `CONTEXT_KIT_TOKEN_ECONOMICS_ROOT` | installed plugin root (Claude fallback: `CLAUDE_PLUGIN_ROOT`) |
| `CONTEXT_KIT_CLAUDE_PROJECTS` | `~/.claude/projects` |
| `CONTEXT_KIT_COPILOT_DB` | `~/.copilot/session-store.db` |

## Tests

```bash
python3 -m unittest discover -s plugins/token-economics/tests -p 'test_*.py'
```

## License

MIT © Mark Beacom
