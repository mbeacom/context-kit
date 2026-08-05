---
name: tool-savings-benchmark
description: "Use when testing whether a tool, flag, or output wrapper reduces tokens, before quoting a savings percentage."
license: MIT
compatibility: "Requires Python 3. The tools under comparison must be installed locally; a missing binary fails the run instead of downgrading it. Optional tiktoken improves counting for OpenAI-family models only."
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash
---

# Tool Savings Benchmark

Measure whether a tool actually reduces tokens on your work, instead of
repeating the percentage on its README.

A published figure describes the author's corpus, their commands, and their
model. Yours differ. The figure may still be right — but until you measure it, it
is a hypothesis, and quoting it as a result is the failure this skill prevents.

## The rule

**A savings number means nothing without evidence the answer survived.**

Discarding output entirely "saves" 100%. So does truncating the one line that
mattered. Any comparison that measures only output size will rank the most
destructive tool first. Every run therefore declares what the output must still
contain, and a run without that assertion cannot produce a quotable result.

## Run it

Resolve the plugin root first. `CONTEXT_KIT_TOKEN_ECONOMICS_ROOT` is set by
you, not by a host, and only Claude Code injects `CLAUDE_PLUGIN_ROOT` — so
neither may exist. The scripts always sit in `scripts/` beside the `skills/`
directory this file was loaded from, which is the fallback that needs no setup:

```bash
ROOT="${CONTEXT_KIT_TOKEN_ECONOMICS_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
# Neither variable set: derive it from this skill's own location, two levels up
# from skills/<name>/SKILL.md.
[ -n "$ROOT" ] || ROOT="<absolute path of the directory holding this SKILL.md>/../.."
```

Export `CONTEXT_KIT_TOKEN_ECONOMICS_ROOT` once to skip that step every run.

Then run it:

```bash
python3 "$ROOT/scripts/benchmark_savings.py" \
  --baseline "rg -n 'func handleAuth' ." \
  --candidate "rtk rg -n 'func handleAuth' ." \
  --must-contain "handleAuth" \
  --runs 3
```

Use `--must-match` for a regex, repeat either flag for several conditions, and
add `--shell` when an arm needs a pipe. `--tokenizer o200k_base` uses tiktoken
when installed; it is valid for OpenAI-family models only, since Anthropic
publishes no offline tokenizer.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `saves` | Material reduction, answer preserved, arms agreed. Quotable. |
| `costs` | The candidate is more expensive. Also a real result. |
| `inconclusive` | Under the 5% materiality threshold — within corpus noise. |
| `unverified` | Something invalidates the comparison. Not quotable at all. |

Exit `0` for the first three, `1` for `unverified`, `2` for a setup error.

A run is `unverified` when no assertion was declared, when either arm failed its
assertion, when the arms disagree on exit status, or when the arms were counted
with different tokenizers. Fix the cause; never report the percentage anyway.

## Choosing the arms

The baseline must be *what the agent runs today*, not a strawman. `cat` versus a
compaction tool proves nothing if no one would have run `cat`. Compare against
the flag you would otherwise reach for — often `rg -c`, `rg -l`, `git diff
--stat`, or `jq -c` — because a plain flag frequently beats a wrapper and is one
less dependency.

Measure per command shape, not per tool. Compaction helps most on verbose,
structured, repetitive output (status, logs, JSON) and can lose on output that is
already terse.

## Interpreting a win honestly

- The result is **causal** for that command on that corpus. Only the command
  changed, so `attribution` is `controlled` — unlike session telemetry, which is
  `observational`.
- The result is **local**. It does not transfer to another repo, another command,
  or a larger corpus without re-measuring.
- Token counts are `estimated` unless a tokenizer ran. Treat the percentage as
  relative size, not an exact billing delta.
- Saved tool output reduces the prompt for the rest of the session, so the effect
  recurs — but the recurring portion is billed at the cache-read rate, not the
  input rate. Do not multiply a one-shot saving by turn count and call it cost.

## References

- `references/compaction-tools.md` — rtk, headroom, and native flags.
- `references/claims.md` — turning a measurement into a defensible statement.

## Portability

```bash
copilot plugin marketplace add mbeacom/context-kit   # GitHub Copilot CLI
copilot plugin install token-economics@context-kit
```

APM and Claude Code install the same plugin with `apm install` and
`/plugin install`. No host exports the plugin root for you: set
`CONTEXT_KIT_TOKEN_ECONOMICS_ROOT` to the installed directory, or rely on the
skill-relative fallback above. In Claude Code, `${CLAUDE_PLUGIN_ROOT}` already
resolves to the same location.
