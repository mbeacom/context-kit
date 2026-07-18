---
name: plan-execute-strategy
description: "Use when deciding HOW to split work between a strong planner and cheaper executors — configuring subagent models, writing delegation prompts, running the plan-big/execute-small workflow, or choosing between delegation and the advisor tool."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Bash
---

# Plan / Execute Strategy

Two inversions of the same idea — *spend strong-model tokens on judgment, cheap
tokens on volume*. Pick by which model you want in the driver's seat.

| Strategy | Who plans | Who executes | Set up with |
| --- | --- | --- | --- |
| **Delegation** | strong **main** model | cheap **subagents** | `CLAUDE_CODE_SUBAGENT_MODEL` + a delegation prompt (this skill) |
| **Advisor** | strong **advisor**, consulted mid-turn | cheap **main** model | `/advisor` (the server-side advisor tool) |

They are orthogonal — you can run both at once (cheap main + strong advisor +
cheaper subagents). This skill is about **delegation**; the advisor tool is
covered at the end so you pick the right one.

## When to use delegation

- The task splits into independent, token-heavy sub-tasks (multi-file audits,
  broad research sweeps, large log/document review).
- You want a strong model (Opus, Fable) to plan and synthesize, but the reading
  and mechanical edits don't need that tier.
- The advisor can't help here — a **Fable 5 main runs without any advisor today**
  (see below), you're off the Anthropic API (Bedrock, Google Cloud, Foundry), or your
  main model doesn't support it — or you specifically want the strong model leading
  rather than merely advising.

## Delegation, interactive

Run the session with a strong **main** model and pin **subagents** to a cheaper
one, then tell the main model to delegate:

```bash
CLAUDE_CODE_SUBAGENT_MODEL=sonnet claude \
  --append-system-prompt "For task execution, delegate to subagents with clear, \
appropriately-scoped instructions. You own planning and oversight of overall \
progress; self-judged exceptions are allowed."
```

Set the main model separately with `/model` (in-session) or `--model` (e.g.
`--model claude-fable-5`). The two knobs are independent: `--model` / `/model`
picks the driver, `CLAUDE_CODE_SUBAGENT_MODEL` picks the workers.

**How the subagent model resolves** (first match wins):

1. `CLAUDE_CODE_SUBAGENT_MODEL` env var (alias — `sonnet` / `opus` / `haiku` /
   `fable` — or a full model ID).
2. The per-invocation `model` passed when the subagent is spawned.
3. The subagent definition's `model:` frontmatter.
4. Otherwise `inherit` (same model as the main conversation). As of v2.1.196,
   setting the env var to `inherit` is the same as leaving it unset.

Subagents also inherit the main conversation's extended-thinking setting
(v2.1.198+).

**Where to put the delegation instruction** — pick one, don't stack them:

- `--append-system-prompt "…"` — session-scoped, nothing left behind. Cleanest
  for a one-off. (This is the recommended default.)
- A custom **output style** (`/output-style`) — persists the delegation posture
  across sessions without editing `CLAUDE.md`.
- `CLAUDE.md` — durable and repo-shared, but it only *steers behavior*; it can't
  set the subagent model (that's the env var / frontmatter above).

## Delegation, scripted

When you want the split to be deterministic and repeatable rather than left to
the model's judgment, run the bundled workflow:

```text
/plan-big-execute-small <task>
```

It runs a strong **planner** (decompose into independent sub-tasks) → cheap
**workers** in parallel (default `haiku`, isolated contexts, distilled findings)
→ a cheap **verifier** (re-checks the workers' claims, read-only) → a strong
**synthesizer** (merge). The command invokes the plugin's
`workflows/plan-big-execute-small.workflow.js` via the `Workflow` tool. Prefer
this over the interactive setup when you need coverage guarantees, a fixed number
of workers, or a barrier before synthesis; prefer interactive when the shape of
the work is still unfolding.

For interactive delegation of a *single* scoped unit, hand it to the
`execution-worker` subagent this plugin ships — a Sonnet-by-default worker (cheaper
than an Opus/Fable planner, capable enough to edit) that does one task and reports
back. Override its model with `CLAUDE_CODE_SUBAGENT_MODEL` (for example `haiku` for
read-only investigation).

> Deferred by design: if a workload ever needs a *guaranteed* read-only lane — e.g.
> many workers on a shared tree — a dedicated `investigation-worker` (tools:
> Read/Grep/Glob only, no Bash/Edit/Write) is the sanctioned next agent to add. It
> isn't shipped yet: one broadly-scoped worker plus these instructions covers the
> current need, and a fleet of specialized agents would fight the "few agents"
> convention while the `CLAUDE_CODE_SUBAGENT_MODEL` override flattens per-agent model
> pins on the scripted path anyway.

## The advisor tool (`/advisor`) — how it differs

`/advisor` (the `advisorModel` setting) is the **server-side advisor tool**: a
*cheaper main model* consults a stronger advisor mid-turn for a plan or course
correction, then keeps executing. It is the inverse of delegation — the strong
model advises rather than leads. What to know before picking it:

- **Capability pairing.** The advisor must be **at least as capable as** the main
  (executor) model — a weak main + strong advisor is the point. An Opus 4.8 main
  accepts Fable, Opus 4.7, or Opus 4.8; a Sonnet 5 or Opus 4.6 advisor is rejected.
  An equal-tier advisor (e.g. Opus main + Opus advisor) is **not** a no-op — it's a
  legitimate independent second read, just not a *stronger* opinion.
- **Fable 5 as the advisor is turned off right now** — a deliberate,
  remotely-controlled rollout, not a billing gate. As of Claude Code v2.1.210+ the
  [advisor doc](https://code.claude.com/docs/en/advisor) says so: the `/advisor`
  picker shows a dimmed `Fable 5 (temporarily unavailable)` row, and Claude Code
  rejects `/advisor fable` and `--advisor fable`. The underlying defect is
  [#76199](https://github.com/anthropics/claude-code/issues/76199) — `advisorModel:
  fable` plus *any* prior `tool_use` in the transcript deterministically returns
  `unavailable` (the executor model is irrelevant, an Opus advisor is immune, and it
  is not a context-size issue). **Use `/advisor opus` instead** — Opus 4.7/4.8 as the
  advisor works today.
- **A Fable 5 main session has no advisor at all.** A Fable main accepts only a
  Fable advisor, and Fable isn't offered, so a Fable 5 session runs advisor-less
  until the rollout returns it. That gap is exactly what delegation (this skill)
  fills: plan big with Fable 5, execute small with cheaper subagents.

Hardening notes (these bite CI and gateway users):

- **Anthropic API only.** The advisor is a server-executed tool — not available on
  Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent Platform, or Microsoft
  Foundry. Through an LLM gateway it works only if the request is forwarded intact. On
  those runtimes, delegation is the fallback.
- **Deterministic off-switch.** `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` disables the
  advisor entirely: `/advisor` becomes unavailable, any `advisorModel` is ignored, and
  `--advisor` is accepted but inert — existing scripts won't error. Clean when you want
  delegation to be the only orchestration in play.
- **Subagents inherit the advisor** and re-check the pairing against their *own* model,
  so a Sonnet subagent under an Opus main can still consult the advisor even where the
  parent pairing couldn't — useful when you combine delegation with an advisor.

Rule of thumb: **cheap main that occasionally needs a smart second opinion →
advisor. Strong main that should offload volume → delegation** (this skill).

## Portability (GitHub Copilot)

GitHub Copilot CLI supports this plugin format directly — no manual file copying.
Register the marketplace and install the plugin:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install plan-execute@context-kit
```

The scripted `Workflow` and `CLAUDE_CODE_SUBAGENT_MODEL` are Claude Code features;
the delegation *posture* (plan strong, execute cheap) applies wherever an agent can
spawn workers.
