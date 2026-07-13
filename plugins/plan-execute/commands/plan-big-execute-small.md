---
description: Run the plan-big/execute-small workflow — a strong planner decomposes the task, cheap workers execute in parallel, a strong synthesizer merges the findings.
argument-hint: <task to decompose and execute>
---

Run the **plan-big / execute-small** workflow bundled with this plugin.

Invoke the `Workflow` tool with:

- `scriptPath`: `${CLAUDE_PLUGIN_ROOT}/workflows/plan-big-execute-small.workflow.js`
  (pass the resolved absolute path; `${CLAUDE_PLUGIN_ROOT}` is this plugin's
  install directory)
- `args`: `{ "task": "$ARGUMENTS" }`

If `$ARGUMENTS` is empty, ask the user what task to run and do **not** invoke the
workflow with an empty task.

The workflow runs a strong planner (inherits the current session model) →
cheap workers in parallel (default `haiku`, isolated contexts, distilled findings)
→ a cheap read-only verifier that re-checks the workers' claims → a strong
synthesizer, and returns `{ plan_summary, subtaskCount, findings, verification,
answer }`. To tune the run, add `workerModel` (default `haiku`) or `maxSubtasks`
(default `16`) to `args`.

When it completes, report the synthesized `answer`, and note how many workers ran
and whether any produced no findings. This is orchestration only — it does not
modify files unless a worker's sub-task explicitly requires it.
