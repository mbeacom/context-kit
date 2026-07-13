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
- You are NOT on the advisor beta, or you specifically want the strong model
  leading rather than merely advising.

## Delegation, interactive

Run the session with a strong **main** model and pin **subagents** to a cheaper
one, then tell the main model to delegate:

```bash
CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-5 claude \
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
→ a strong **synthesizer** (merge). The command invokes the plugin's
`workflows/plan-big-execute-small.workflow.js` via the `Workflow` tool. Prefer
this over the interactive setup when you need coverage guarantees, a fixed number
of workers, or a barrier before synthesis; prefer interactive when the shape of
the work is still unfolding.

For interactive delegation of a *single* scoped unit, hand it to the
`execution-worker` subagent this plugin ships (a cheap-model worker that does one
task and reports back).

## The advisor tool (`/advisor`) — how it differs

`/advisor` (the `advisorModel` setting) is the **server-side advisor tool**: a
*cheaper main model* consults a stronger advisor mid-turn for a plan or course
correction, then keeps executing. It is the inverse of delegation — the strong
model advises rather than leads. Two constraints worth knowing:

- The advisor must be **at least as capable as** the main (executor) model. So a
  weak main + strong advisor is the point; a **Fable main with a Fable advisor is
  a no-op** self-consult.
- It is a beta feature and may not be enabled on every account. If `/advisor`
  reports a model but consults never fire, the entitlement isn't active — fall
  back to delegation, which needs no beta.

Rule of thumb: **cheap main that occasionally needs a smart second opinion →
advisor. Strong main that should offload volume → delegation** (this skill).

## Portability (GitHub Copilot)

This skill is portable. In Copilot, copy this folder to
`.github/skills/plan-execute-strategy/` or `~/.copilot/skills/`. The scripted
workflow and `CLAUDE_CODE_SUBAGENT_MODEL` are Claude Code features; the delegation
*posture* (plan strong, execute cheap) applies wherever an agent can spawn
workers.
