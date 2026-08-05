---
description: Report local agent token usage with per-host correctness rules
argument-hint: "[claude|copilot|both]"
disable-model-invocation: true
---

Report token usage from local host records.

```text
$ARGUMENTS
```

Apply the `token-accounting` skill. Treat empty `$ARGUMENTS` as both hosts.

Run the collector rather than summing records by hand — the deduplication and
per-host cache decomposition it performs are the reason the totals are correct:

```bash
python3 "$ROOT/scripts/collect_usage.py" --host claude --host copilot
```

`$ROOT` is the installed plugin directory. Use
`CONTEXT_KIT_TOKEN_ECONOMICS_ROOT` when the user has exported it, or
`CLAUDE_PLUGIN_ROOT` under Claude Code. When neither is set — the default after
a `copilot plugin install` — resolve it from the `token-accounting` skill's own
location, since `scripts/` is a sibling of `skills/`.

Restrict `--host` when the argument names one. Add `--format json` when the
caller wants the raw record.

Exit `1` means no records were found. Report the source as absent; do not report
zero usage.

Then summarize for a decision-maker:

- Report token classes separately and quote the cache hit ratio. A single total
  hides the economics, since cache reads are cheap and dominate volume.
- Report cost only where the host recorded it. Copilot records AI Units; Claude
  Code records none, so any currency figure is an assumption and must be labelled
  as one.
- Label the figures `counting: exact` and `attribution: observational`.
- State explicitly that these records cannot attribute usage to any tool or
  practice. If the caller wants that, use `/benchmark-tool-savings`.

Do not project the numbers forward or convert subscription usage into money.
