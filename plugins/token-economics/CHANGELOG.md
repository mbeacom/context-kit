# Changelog

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
