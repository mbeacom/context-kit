# Reporting

A usage report is read by someone deciding whether to change how a team works.
State what was measured, in the unit it was measured in, with the limits
attached — and make the honest version easy to act on rather than merely hedged.

## State both grades

Every figure carries two:

- **Counting** — `exact` (host-recorded) or `estimated` (heuristic).
- **Attribution** — `observational` (telemetry) or `controlled` (A/B).

Everything read from session records is `observational`, however precise the
count. Precision is not causation, and a report that omits attribution invites
the reader to supply the causal claim themselves.

## Report token classes separately

A single total hides the economics, because classes differ by an order of
magnitude in price:

```text
input (uncached)     5,245,579
cache read       2,716,995,667
cache write         88,140,400
output               5,446,550
cache hit ratio          96.7%
```

Cache reads dominate volume and are cheap. Uncached input is a rounding error by
volume and expensive per token. Collapsing these into "2.8B tokens" makes a
cheap, well-cached workload look alarming.

A falling cache hit ratio is usually the most actionable signal in the report: it
means prompt prefixes are being invalidated, which raises cost without any change
in work done.

## Currency

Report cost only where the host recorded it.

- Copilot CLI: exact, in AI Units, from `total_nano_aiu`. Do not convert to
  currency without the actual contract price.
- Claude Code: no cost recorded. Report tokens.

On a subscription plan the marginal cost of a token is zero. A dollar figure
there is fabricated; the real constraints are quota and context window, so report
capacity rather than money.

## Paths

`collect_usage.py` prints `source` home-relative (`~/.claude/projects`) so a
pasted report does not name the developer or expose machine layout. `--raw-paths`
restores absolute paths for local debugging; prefer the default in anything
shared.

## Absence is not zero

If no records were found, say the source was absent. `collect_usage.py` exits `1`
for this and never prints a zero total as if it were a measurement.

## What not to write

- **"Tool X saved us N tokens"** from telemetry. Telemetry cannot attribute.
  Either run the controlled comparison or drop the claim.
- **A currency figure on a subscription plan.** No such money was spent.
- **A total priced from a raw `input_tokens` column.** Confirm the host's cache
  semantics first; the two hosts are opposites.
- **A percentage without its denominator.** "40% fewer tokens" is unreadable
  without knowing 40% of which class, over what period.
- **A projection.** "This will save $X/year" multiplies an observational number
  by an assumed constant workload. Report what happened.

## A usable shape

```markdown
## Token usage — <scope>, <date range>

Counting: exact (host-recorded). Attribution: observational.

| Class | Tokens |
| --- | --- |
| input (uncached) | … |
| cache read | … |
| cache write | … |
| output | … |

Cache hit ratio: …%
Recorded cost: … AIU (Copilot) / not recorded (Claude Code)
Deduplication: … replayed records excluded.

Reads as: <one sentence a decision-maker can act on>.
Not established: which tools or practices caused this.
```

That final pair of lines is the point. The report ends with the one conclusion
the data supports and an explicit statement of the one it does not — which is
usually the question that prompted the report. If a causal answer is needed, hand
the specific claim to `tool-savings-benchmark`, and route any figure you intend
to quote to others through `verify-before-trust`.
