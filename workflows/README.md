# Workflows

Reusable [Claude Code Workflow](https://docs.claude.com/en/docs/claude-code) scripts —
deterministic multi-agent orchestration you run with the `Workflow` tool. These are
templates, not installed plugin capabilities; copy or adapt them freely.

## `plan-big-execute-small.workflow.js`

The "plan big, execute small" (coordinator/worker) pattern, expressed with native
Claude Code subagents instead of the Managed Agents API:

- **Plan** — one strong agent (inherits the session model) decomposes the task into
  independent sub-tasks. It never reads raw material.
- **Execute** — many cheap workers (a model override, default `haiku`) each handle one
  sub-task in an isolated context and report back *distilled* findings.
- **Synthesize** — one strong agent merges the findings into the final answer.

The leverage is rate/quota arbitrage plus parallelism: the token-heavy reading happens
at the worker model's rate while planning and synthesis stay frontier-quality.

### How it relates to the advisor tool

These are two inversions of the same "cheap where you can, strong where it counts" idea:

| | Who leads | Who is consulted | Where it runs |
| --- | --- | --- | --- |
| **Advisor tool** (`/advisor`) | weak executor | strong advisor, mid-turn | native, in-band, one request |
| **This workflow** | strong planner | cheap workers, delegated | subagents, fanned out |

Reach for the advisor tool when a mostly-mechanical session occasionally needs a
strong second opinion. Reach for this workflow when the task splits cleanly into
independent, token-heavy sub-tasks that a strong model should plan and synthesize.

### Run it

```text
Workflow({
  scriptPath: "workflows/plan-big-execute-small.workflow.js",
  args: { task: "Audit every route handler in app/ for missing auth checks", workerModel: "haiku", maxSubtasks: 12 }
})
```

Or copy it into `.claude/workflows/` (repo- or user-level) to invoke it by name:

```text
Workflow({ name: "plan-big-execute-small", args: { task: "…" } })
```

### Arguments

`args` may be a bare string (the task) or an object:

| Field | Default | Meaning |
| --- | --- | --- |
| `task` | *required* | The overall task to decompose. |
| `workerModel` | `haiku` | The cheap executor model for the workers. |
| `workerEffort` | `low` | Reasoning effort for the workers. |
| `maxSubtasks` | `16` | Caps the fan-out; excess sub-tasks are dropped (and logged). |

### Adapt it

- **Scope the workers.** The template's workers inherit whatever tools the workflow
  subagent has. For read-only sweeps, pass an `agentType` with a read-only tool set so
  workers can't mutate files.
- **Add a verify pass.** Insert a stage between Execute and Synthesize that
  adversarially checks each finding (see the `Workflow` tool's review pattern) when
  correctness matters more than speed.
- **Right-size the fan-out.** Prefer the fewest sub-tasks that fully cover the task —
  over-splitting adds coordination overhead, under-splitting loses parallelism.
