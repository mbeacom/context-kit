# plan-execute

!!! abstract "Plan big, execute small"
    A strong model plans and delegates token-heavy work to cheaper executors. The
    leverage is rate/quota arbitrage plus parallelism — planning and synthesis
    stay frontier-quality while the bulk reading and mechanical work runs at a
    cheaper model's rate.

## Install

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install plan-execute@context-kit
    ```

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install plan-execute@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install plan-execute@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`plan-execute-strategy`** skill | When and how to split work: the `CLAUDE_CODE_SUBAGENT_MODEL` + `--append-system-prompt` delegation recipe, the `/output-style` option, and how the `/advisor` tool differs. |
| **`/plan-big-execute-small`** command | Runs the bundled workflow: strong planner → cheap parallel workers → cheap read-only verifier → strong synthesizer. |
| **`plan-big-execute-small`** workflow | The script the command runs (`workflows/plan-big-execute-small.workflow.js`); also runnable directly by path. |
| **`execution-worker`** subagent | A cheap-model, tightly-scoped worker for delegating a single sub-task interactively. |

## Two ways to use it

**Interactive** — put a strong model in the driver's seat and pin subagents to a
cheaper one:

```bash
CLAUDE_CODE_SUBAGENT_MODEL=sonnet claude \
  --append-system-prompt "Delegate execution to subagents with clear, scoped \
instructions; you own planning and oversight."
```

**Scripted** — for a deterministic, repeatable split:

```text
/plan-big-execute-small <task>
```

## Running the workflow directly

The command invokes the workflow via `${CLAUDE_PLUGIN_ROOT}`. You can also run it
yourself:

```text
Workflow({
  scriptPath: "<plugin dir>/workflows/plan-big-execute-small.workflow.js",
  args: { task: "…", workerModel: "haiku", maxSubtasks: 12 }
})
```

`args` accepts a bare task string or `{ task, workerModel?, workerEffort?,
maxSubtasks? }`. The planner and synthesizer inherit the session model; the
workers and the read-only verifier run at `workerModel` (default `haiku`).

## Relationship to the advisor tool

Delegation (this plugin) and the `/advisor` tool are inverses of the same "strong
where it counts, cheap where you can" idea: delegation puts the strong model in
front leading and delegating; the advisor puts a cheap model in front and lets it
consult a stronger advisor mid-turn. They're orthogonal and can be combined — the
`plan-execute-strategy` skill explains when to reach for each.

## At a glance

| | |
| --- | --- |
| **Category** | orchestration |
| **Provides** | skill, `/plan-big-execute-small` command, workflow, `execution-worker` subagent |
| **Dependencies** | none |
| **License** | MIT |
