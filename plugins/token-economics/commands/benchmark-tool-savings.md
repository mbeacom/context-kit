---
description: Measure whether a tool actually reduces tokens, with a controlled A/B run
argument-hint: "<tool or claim to test>"
disable-model-invocation: true
---

Settle this token-savings claim by measurement:

```text
$ARGUMENTS
```

If `$ARGUMENTS` is empty, ask which tool, flag, or wrapper is in question and
stop.

Apply the `tool-savings-benchmark` skill.

First establish the three inputs, asking the caller when they are not obvious
from the request:

1. **Baseline** — the command an agent runs *today*. Not a strawman. If a native
   flag such as `rg -c`, `rg -l`, `git diff --stat`, or `jq -c` would already
   answer the question, benchmark against that instead; a wrapper must beat the
   realistic alternative to be worth installing.
2. **Candidate** — the command being claimed as cheaper.
3. **Preserved answer** — what the output must still contain for the task to have
   succeeded. This is mandatory. Without it, discarding output scores as a
   perfect saving.

Then run it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/benchmark_savings.py" \
  --baseline "<baseline>" \
  --candidate "<candidate>" \
  --must-contain "<answer that must survive>" \
  --runs 3
```

Add `--shell` when an arm needs a pipe, `--must-match` for a regex, and
`--tokenizer o200k_base` for OpenAI-family models when tiktoken is installed.

Report the verdict as returned:

- `saves` or `costs` — a real result. Report the magnitude with the command pair,
  the corpus, the counting grade, and the assertion that held.
- `inconclusive` — under the materiality threshold. Do not present it as a win.
- `unverified` — the comparison is invalid. Report the stated problem and fix it.
  Never quote the percentage from an unverified run.

Scope the conclusion to the command pair and corpus actually measured. Do not
generalize to other commands, other repositories, or an annual figure, and do not
convert tokens to money unless usage is metered and the price is known.
