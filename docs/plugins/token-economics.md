# token-economics

!!! abstract "Measure token spend, and prove a savings claim instead of quoting one"
    The catalog recommends tools that claim to cut tokens — `rtk`, compaction
    proxies, narrower flags. This plugin is how those claims get checked, and how
    a usage report survives someone reading it closely.

`token-economics` declares `dependencies: ["verify"]`. A savings figure is a
claim about the world, so anything you intend to quote to someone else belongs in
[`verify`](verify.md)'s verdict flow. `verify` already pulls the
[retrieval spine](retrieval-core.md).

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install token-economics@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install token-economics@context-kit   # also deploys verify
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install token-economics@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`token-accounting`** skill | Read Claude Code and Copilot CLI usage records correctly: deduplicate replayed responses, decompose cache traffic per host, and grade every figure. |
| **`tool-savings-benchmark`** skill | Settle a savings claim with a controlled A/B run that must preserve the answer. |
| **`/token-report`** command | Usage report from local host records. |
| **`/benchmark-tool-savings`** command | Runs the controlled comparison for one claim. |
| **`collect_usage.py`** | Standard-library, read-only reader for both hosts. |
| **`benchmark_savings.py`** | A/B runner returning `saves`, `costs`, `inconclusive`, or `unverified`. |

## The arithmetic is not obvious

Each host stores usage in a shape whose natural reading is wrong. Measured on a
live developer machine:

| Trap | Effect |
| --- | --- |
| Claude Code replays responses into resumed sessions and subagent transcripts | **60.4%** of records are duplicates; naive summing overstates tokens by **132.6%** |
| Copilot's `input_tokens` **includes** cache traffic; Claude Code's **excludes** it | pricing the raw column overstated uncached input by ~**950×** |
| Cache reads are ~**97%** of input-side tokens and bill at ~a tenth of the input rate | a token total says little about spend |

Deduplication keys on `(requestId, message.id)` — both, because one request can
stream several messages while the same message is copied into subagent files.

Copilot rows carry their own per-model rate card in `token_details_json`, so cost
is exact and needs no price table; the identity `total_nano_aiu == Σ (tokenCount
/ batchSize) × costPerBatch` held on 400 of 400 sampled rows. Claude Code records
no cost at all, so any currency figure there is your own assumption.

## Measurement is not attribution

This is the distinction the plugin exists to hold.

| | Session telemetry | Controlled A/B |
| --- | --- | --- |
| Question | what did we spend? | did this tool cause a saving? |
| Attribution | `observational` | `controlled` |
| Supports "usage fell" | yes | yes |
| Supports "tool X caused it" | **no** | yes |

Usage falling after adopting a tool does not show the tool caused it — the work
changed too. No dashboard fixes this, because neither host records which tool
call produced which tokens. Aggregating more machines raises confidence in the
*measurement* and never in the *causal claim*.

Every figure therefore carries two grades: **counting** (`exact` or `estimated`)
and **attribution** (`controlled` or `observational`).

## A savings number needs a preserved answer

Discarding output entirely "saves" 100%. So does truncating the one line that
mattered. A comparison measuring only output size ranks the most destructive tool
first.

So every benchmark declares what the output must still contain:

```bash
python3 plugins/token-economics/scripts/benchmark_savings.py \
  --baseline "rg -n 'func handleAuth' ." \
  --candidate "rtk rg -n 'func handleAuth' ." \
  --must-contain "handleAuth" --runs 3
```

A run without that assertion cannot produce a quotable result — it is reported
`unverified` and exits non-zero. `--no-assertion` is allowed but permanently
downgrades the verdict rather than silently blessing it.

| Verdict | Meaning |
| --- | --- |
| `saves` | Material reduction, answer preserved, arms agreed. Quotable. |
| `costs` | The candidate is more expensive. Also a real result. |
| `inconclusive` | Under the 5% materiality threshold — within corpus noise. |
| `unverified` | Something invalidates the comparison. Not quotable at all. |

A run is `unverified` when no assertion was declared, when either arm failed it,
when the arms disagree on exit status, or when they were counted with different
tokenizers.

## Pick an honest baseline

The baseline must be what an agent runs *today*. A wrapper that beats `cat` but
loses to `rg -c` has not earned an install, and the native flag is one less
dependency in the path of everything the agent reads.

Compaction pays most on verbose, structured, repetitive output and least on
output that is already terse — which is why `headroom` advertises 15–20% for
coding agents but 60–95% for JSON. Which regime your commands fall into is
exactly what the benchmark decides.

## Scale

Fleet rollups are asymmetric between hosts:

- **Claude Code** exports OpenTelemetry. `claude_code.token.usage` carries a
  `type` attribute in **camelCase** (`input`, `output`, `cacheRead`,
  `cacheCreation`) — splitting on snake_case silently yields empty series — plus
  `query_source` (`main`, `subagent`, `auxiliary`), the only supported way to
  separate delegated work at scale.
- **GitHub Copilot CLI** exports no token telemetry. Its organization APIs report
  engagement, not tokens, so they cannot answer a spend question.

Scale up only when a decision depends on it, collect counts rather than content,
and keep the content-logging flags off. Nothing in this plugin sends data
anywhere.

## Configuration

| Variable | Default |
| --- | --- |
| `CONTEXT_KIT_CLAUDE_PROJECTS` | `~/.claude/projects` |
| `CONTEXT_KIT_COPILOT_DB` | `~/.copilot/session-store.db` |

Both host formats are internal and carry no stability guarantee. The reader
degrades to a disclosed gap rather than a wrong number, and reports an absent
source as absent — never as zero usage.

## Tests

```bash
python3 -m unittest discover -s plugins/token-economics/tests -p 'test_*.py'
```
