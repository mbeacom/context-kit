# Changelog

## 0.2.0 — 2026-08-04

Changes from a five-lens deep review of the initial implementation.

- Count UTF-8 **bytes** rather than code points in the token heuristic. Counting
  characters scored a 4-byte glyph as a quarter token, which inverted the
  verdict: a candidate emitting twice the bytes was reported as `saves` at
  +49.5%. It now reports `costs`.
- Stop emitting `saved_tokens` / `saved_pct` on an `unverified` run. The raw
  figures moved to `size_delta_*`, so a reader or script can no longer quote a
  number under a savings name from a comparison the tool just refused to stand
  behind.
- Bound captured output at 64 MiB (`--max-capture-bytes`). An arm that floods
  stdout is stopped and its measurement rejected rather than buffered whole; a
  truncated arm can never produce a saving, since a stopped capture is a floor.
- Enforce the timeout with a watchdog and run each arm in its own session,
  killing the process group. A blocking read could not observe a deadline, so a
  quiet long-running arm hung indefinitely and left descendants running.
- Surface Claude Code schema drift: records carrying a usage object with none of
  the known token fields are counted and disclosed, and `counting` downgrades to
  `unknown` when no record was recognized, instead of reporting a confident
  `exact` zero after a host format change.
- Print `source` home-relative by default so a shared report does not carry an
  absolute home path; `--raw-paths` opts out.
- Put the `CLAUDE_PLUGIN_ROOT` fallback in the runnable skill blocks, which
  previously failed outright when the neutral root variable was unset.
- Warn that `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` attaches a person-identifying
  attribute that turns a cost rollup into a per-developer activity dashboard,
  and that benchmark JSON records commands verbatim before it is shared.
- Cover the plugin with the repo's `ruff` and `ruff-format` hooks, which
  previously matched none of its files.

## 0.1.0 — 2026-08-04

- Add the `token-accounting` skill: read Claude Code and GitHub Copilot CLI local
  usage records correctly. Deduplicates replayed responses on
  `(requestId, message.id)` and decomposes cache traffic per host, because the
  two stores mean opposite things by `input_tokens` — Copilot's includes cache
  traffic while Claude Code's excludes it, so the naive reading is wrong in
  opposite directions.
- Add the `tool-savings-benchmark` skill: settle a savings claim with a
  controlled A/B run that requires a preserved-answer assertion, since discarding
  output "saves" 100% and any size-only comparison ranks the most destructive
  tool first.
- Add `scripts/collect_usage.py`, a standard-library read-only reader for both
  hosts. Exits `1` when no records exist, so an absent source is never reported
  as zero usage.
- Add `scripts/benchmark_savings.py`, a controlled A/B runner returning `saves`,
  `costs`, `inconclusive`, or `unverified`. A run without an assertion, with a
  failed assertion, with divergent exit statuses, or with mixed tokenizers is
  `unverified` and exits nonzero rather than yielding a quotable percentage.
- Add the `/token-report` and `/benchmark-tool-savings` commands.
- Report cost only in the unit a host recorded: Copilot rows carry their own
  per-model rate card in `token_details_json`, and Claude Code records no cost at
  all, so a currency figure there is the caller's own assumption.
- Grade every figure with a counting grade (`exact` or `estimated`) and an
  attribution grade (`controlled` or `observational`). Session telemetry is
  always observational and cannot attribute a change to a tool.
- Add references for host data sources, fleet telemetry, reporting, compaction
  tools, and defensible claims.
