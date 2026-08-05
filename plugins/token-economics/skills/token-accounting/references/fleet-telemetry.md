# Fleet telemetry

Local files answer questions about one machine. Rolling measurement up to a team
needs a different pipeline per host, and the two hosts are not symmetric: only
one of them exports token counts at all.

Scale this up only when a decision depends on it. A fleet pipeline is standing
infrastructure with privacy obligations; a one-off question is better answered by
`collect_usage.py` on a few machines.

## Claude Code: OpenTelemetry

Claude Code exports OTel metrics and events. Documentation:
<https://code.claude.com/docs/en/monitoring-usage>.

Enable with `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus standard OTel configuration —
`OTEL_METRICS_EXPORTER` (`otlp`, `prometheus`, `console`, `none`),
`OTEL_LOGS_EXPORTER`, `OTEL_EXPORTER_OTLP_PROTOCOL` (no default; set it
explicitly), `OTEL_EXPORTER_OTLP_ENDPOINT`, and `OTEL_EXPORTER_OTLP_HEADERS`.
Metrics export every 60s and logs every 5s by default.

Exported metrics, all counters:

| Metric | Unit |
| --- | --- |
| `claude_code.session.count` | none |
| `claude_code.lines_of_code.count` | none |
| `claude_code.pull_request.count` | none |
| `claude_code.commit.count` | none |
| `claude_code.cost.usage` | USD |
| `claude_code.token.usage` | tokens |
| `claude_code.code_edit_tool.decision` | none |
| `claude_code.active_time.total` | s |

`claude_code.token.usage` carries a `type` attribute whose values are
**camelCase**: `input`, `output`, `cacheRead`, `cacheCreation`. Splitting on
snake_case silently yields empty series. Also present: `model`, and
`query_source` (`main`, `subagent`, `auxiliary`) — the only supported way to
separate delegated work from main-loop work at fleet scale.

Cardinality controls (`OTEL_METRICS_INCLUDE_SESSION_ID`,
`OTEL_METRICS_INCLUDE_VERSION`, `OTEL_METRICS_INCLUDE_ACCOUNT_UUID`) exist
because session-scoped attributes explode series counts. Turn them off unless a
question needs per-session granularity.

Prompt and tool content is redacted by default. `OTEL_LOG_USER_PROMPTS`,
`OTEL_LOG_TOOL_DETAILS`, and `OTEL_LOG_RAW_API_BODIES` opt in to sending
developer content off-machine. Treat enabling them as a privacy decision with
review, not a config tweak.

`claude_code.cost.usage` is the host's own USD figure and is authoritative in a
way the local transcripts are not — the transcripts record no cost at all.

## GitHub Copilot CLI: no token export

No OpenTelemetry support and no lifecycle hook interface are documented for the
Copilot CLI. Fleet measurement therefore has no push path; the local SQLite store
is the only source of token counts, and collecting it means collecting from each
machine.

The organization APIs report **engagement, not tokens**: active and engaged user
counts, and per-surface breakdowns such as IDE chat and completions. They cannot
answer "how many tokens did we spend" or "what did this tool save." Use them for
adoption questions and say plainly that token economics is out of their scope.

Because per-seat billing is a fixed subscription rather than metered tokens,
"cost saved" at the org level is usually the wrong frame entirely. The economic
question is capacity: whether work fits inside premium-request quota and the
context window, not whether a bill fell.

## Choosing a rollup

| Question | Path |
| --- | --- |
| What did this machine spend? | `collect_usage.py`, both hosts |
| What is the fleet spending over time? | Claude Code OTel to your collector |
| Which models dominate cost? | OTel `model` attribute, or local `by_model` |
| Is delegation actually cheaper? | OTel `query_source`, then a controlled A/B |
| Who is using Copilot? | Copilot org metrics API (engagement only) |
| Did this tool save tokens? | `tool-savings-benchmark` — never telemetry |

That last row is the one to hold. A fleet dashboard shows a trend; it cannot
attribute a change to a tool, because everything else moved too. Aggregation
raises confidence in the *measurement*, never in the *causal claim*.

## Privacy

Usage records are derived from developer activity. Before centralizing anything:
collect counts rather than content, keep content-logging flags off, prefer
aggregates over per-session series, set a retention period, and tell people what
is collected. Nothing in this plugin sends data anywhere; a fleet pipeline is a
deliberate step you take yourself.
