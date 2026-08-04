# deep-review

Multi-lens evaluative review of a change, design, or plan. Retrieval finds
material, `verify` settles whether a claim is true, and `corpus-review` proves
everything was read — this plugin answers the remaining question: **is this
good, and what will go wrong?**

Independent lenses read the same artifact under charters that say what each is
responsible for *and* what it must stay silent about. Findings are typed, so a
checkable assertion routes to `verify` while a preference is labeled as one that
the author may decline. Adjudication merges agreement into confidence rather
than volume, and preserves disagreement as a decision for a human.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install deep-review@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install deep-review@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install deep-review@context-kit
```

The plugin depends on `verify` to adjudicate the defect claims it deliberately
refuses to settle itself, and on `plan-execute` for per-lens fan-out; `verify`
already pulls the `retrieval-core` spine. The bundled script needs Python 3 and
uses only the standard library.

## Components

| Component | Purpose |
| --- | --- |
| **`deep-review`** skill | The frame → lenses → dispatch → adjudicate → route → report pipeline, the finding taxonomy, and the anti-theater rules. |
| **`review-lens`** agent | Reviews one artifact through one assigned charter and returns typed, cited findings plus its own coverage. Read-only. |
| **`/deep-review`** command | Runs the panel end to end over an artifact. |
| **`adjudicate-findings.py`** script | Validates the contract, merges corroboration, flags tradeoff candidates, and emits the review ledger. |

One worker parameterized by a charter, not one agent per persona: a fixed roster
would hardcode which perspectives exist, while a charter is data you can extend
with a domain lens (security, accessibility, privacy, cost) without shipping a
new component.

## Default lenses

| Lens | Responsible for | Silent about |
| --- | --- | --- |
| `adversarial` | making it fail: edge cases, error paths, concurrency, trust boundaries | style, structure, docs, design direction |
| `architect` | coherence with the existing system, coupling, precedent, evolution cost | bug hunting, runtime failure modes, tooling |
| `consumer` | the artifact as experienced: API shape, defaults, error messages, migration burden | internals, implementation quality, deployment |
| `operator` | day two: detectability, diagnosability, reversibility, on-call burden | elegance, API taste, code style |

The non-scope column is the load-bearing one. Without it, four lenses all file
the same naming complaint and the panel becomes an echo.

## Usage

```bash
ROOT="${CONTEXT_KIT_DEEP_REVIEW_ROOT:-$CLAUDE_PLUGIN_ROOT}"

# frame.json declares the artifact, the decision, the stakes, and the
# expected_lenses roster; dispatch one review-lens worker per charter
# -> ./work/findings/<lens>.md

python3 "$ROOT/scripts/adjudicate-findings.py" \
  --frame ./work/frame.json \
  --findings-dir ./work/findings \
  --out-dir ./work/report
```

Adjudication exits nonzero when a declared lens is missing, a report is
malformed, or a finding violates the contract — a degraded panel cannot be
reported as a complete one.

## The three rules that matter

**Every finding is typed, and the type is a commitment.** A `DEFECT` must carry
a concrete falsification; a `RISK` must name its trigger. A defect you cannot
exhibit is a risk, and a risk with no trigger is a judgment. This is what
separates red-teaming from nitpicking, and it is enforced by the script rather
than requested in prose.

**Corroboration merges, never multiplies.** Two lenses reaching the same finding
collapse into one entry carrying both lenses and the highest severity either
asserted. Counting agreement three times destroys the exact signal that running
independent lenses was supposed to produce — and it only means anything because
no lens ever sees another's findings.

**Disagreement is preserved, never resolved.** When two lenses want different
things at the same location, that is a tradeoff candidate routed to whoever owns
the decision — including when they agreed on the problem and split only on the
fix, since every lens's resolution survives the merge. A synthesizer that quietly picks a winner discards the most
valuable output of a multi-perspective review.

A fourth, borrowed from `corpus-review`: findings are reported with coverage. A
findings list alone reads as approval of everything it does not mention, and a
lens that crashed says nothing about its charter — it does not say the artifact
is fine.

## Development

```bash
python3 -m unittest discover -s plugins/deep-review/tests -p 'test_*.py'
```

The tests are hermetic: no network, no model, temporary directories only.
