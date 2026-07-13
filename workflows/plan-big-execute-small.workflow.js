// plan-big-execute-small.workflow.js
//
// A reusable Claude Code Workflow template implementing the "plan big, execute
// small" (coordinator/worker) pattern from the Anthropic managed-agents cookbook,
// expressed with native Claude Code subagents instead of the Managed Agents API.
//
//   Plan       — one STRONG agent (inherits the session model) decomposes the
//                task into independent sub-tasks. It never touches raw material.
//   Execute    — many CHEAP workers (model override) each handle ONE sub-task in
//                their own isolated context and report back distilled findings.
//   Synthesize — one STRONG agent merges the distilled findings into the answer.
//
// The leverage is rate/quota arbitrage + parallelism: the bulk of the token-heavy
// reading happens at the worker model's rate, while planning and synthesis stay
// frontier-quality. This is the CC-native cousin of the API "advisor tool" — there
// the weak model leads and consults a strong advisor mid-turn; here a strong model
// leads and delegates to weak workers. Use whichever inversion fits the task.
//
// Run it:
//   Workflow({ scriptPath: "workflows/plan-big-execute-small.workflow.js",
//              args: { task: "…", workerModel: "haiku", maxSubtasks: 12 } })
//
// Or drop it in .claude/workflows/ (repo- or user-level) to invoke by name:
//   Workflow({ name: "plan-big-execute-small", args: { task: "…" } })
//
// `args` may be a bare string (the task) or an object:
//   { task, workerModel?, workerEffort?, maxSubtasks? }

export const meta = {
  name: 'plan-big-execute-small',
  description:
    'Strong planner decomposes a task; cheap workers execute the sub-tasks in parallel; strong synthesizer merges the distilled findings.',
  whenToUse:
    'Token-heavy coverage work that splits into independent sub-tasks — multi-file audits, broad research sweeps, large log/document reviews — where planning + synthesis want a strong model but the reading is mechanical.',
  phases: [
    { title: 'Plan', detail: 'Strong model decomposes the task into independent sub-tasks' },
    { title: 'Execute', detail: 'Cheap workers each handle one sub-task in an isolated context' },
    { title: 'Synthesize', detail: 'Strong model merges the distilled findings into the answer' },
  ],
}

// ---- inputs -----------------------------------------------------------------

const TASK =
  typeof args === 'string'
    ? args
    : args && typeof args.task === 'string'
      ? args.task
      : null

if (!TASK) {
  // Fail loud rather than silently planning nothing.
  throw new Error(
    'plan-big-execute-small: no task provided. Pass args as a string, or { task: "…" }.'
  )
}

const WORKER_MODEL = (args && args.workerModel) || 'haiku' // the "execute small" lever
const WORKER_EFFORT = (args && args.workerEffort) || 'low' // cheap, mechanical work
const MAX_SUBTASKS = (args && args.maxSubtasks) || 16 // cap the fan-out

// ---- schemas (validated at the tool-call layer; agents retry on mismatch) ---

const PLAN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['plan_summary', 'subtasks'],
  properties: {
    plan_summary: {
      type: 'string',
      description: 'One or two sentences on how the task was decomposed.',
    },
    subtasks: {
      type: 'array',
      description: 'Independent, non-overlapping units of work a worker can do alone.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'title', 'instructions'],
        properties: {
          id: { type: 'string', description: 'Short stable slug, e.g. "auth-flow".' },
          title: { type: 'string' },
          instructions: {
            type: 'string',
            description:
              'Everything the worker needs to do this unit WITHOUT seeing the others. Name the exact files/paths/queries to inspect and what to report back.',
          },
        },
      },
    },
  },
}

const FINDING_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['subtask_id', 'summary', 'findings'],
  properties: {
    subtask_id: { type: 'string' },
    summary: { type: 'string', description: 'Distilled answer for this sub-task, a few sentences.' },
    findings: {
      type: 'array',
      description: 'Discrete facts/observations, each with a file:line or source pointer where possible.',
      items: { type: 'string' },
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    unresolved: {
      type: 'array',
      description: 'Anything the worker could not determine within its scope.',
      items: { type: 'string' },
    },
  },
}

// ---- prompts ----------------------------------------------------------------

const plannerPrompt = (task) => `You are the PLANNER in a plan-big / execute-small pipeline.

TASK:
${task}

Decompose this into independent, non-overlapping sub-tasks that cheap workers can
each carry out ALONE, in parallel, without seeing each other's work. Aim for the
smallest number of sub-tasks that fully covers the task (target ${MAX_SUBTASKS} or
fewer — over-splitting adds coordination overhead, under-splitting loses parallelism).

You do the thinking; the workers do the reading. For each sub-task, write
self-contained instructions that name the exact files, paths, queries, or sources
to inspect and state precisely what to report back. Do NOT read source material
yourself — that is the workers' job. Return the plan via the structured output.`

const workerPrompt = (task, st) => `You are a WORKER handling ONE sub-task of a larger effort.
You will NOT see the other workers or the final synthesis — report back everything relevant.

OVERALL TASK (context only):
${task}

YOUR SUB-TASK — "${st.title}" [${st.id}]:
${st.instructions}

Do exactly this sub-task: inspect the named material, then report DISTILLED findings
(not raw dumps). Cite file:line or source for each finding where you can. If something
is outside your scope or undeterminable, put it under "unresolved" rather than guessing.
Return your result via the structured output.`

const synthPrompt = (task, distilled) => `You are the SYNTHESIZER in a plan-big / execute-small pipeline.
The token-heavy reading is done; ${distilled.length} worker(s) reported distilled findings below.

OVERALL TASK:
${task}

WORKER FINDINGS (JSON):
${JSON.stringify(distilled, null, 2)}

Merge these into a single, coherent answer to the task. Resolve overlaps and any
contradictions between workers (prefer higher-confidence, better-cited findings, and
flag genuine conflicts rather than hiding them). Carry the workers' file:line / source
pointers through into your answer. Call out anything still unresolved. Do not re-read
source material — synthesize only from the findings above plus the task.`

// ---- pipeline ---------------------------------------------------------------

phase('Plan')
const plan = await agent(plannerPrompt(TASK), {
  label: 'planner',
  phase: 'Plan',
  schema: PLAN_SCHEMA,
}) // planner inherits the (strong) session model — do NOT override it

const subtasks = ((plan && plan.subtasks) || []).slice(0, MAX_SUBTASKS)
if ((plan && plan.subtasks ? plan.subtasks.length : 0) > MAX_SUBTASKS) {
  log(`Planner returned ${plan.subtasks.length} sub-tasks; capping at ${MAX_SUBTASKS}.`)
}
log(`Plan: ${plan ? plan.plan_summary : '(planner returned nothing)'} — ${subtasks.length} sub-task(s)`)

if (subtasks.length === 0) {
  return { task: TASK, plan, subtaskCount: 0, findings: [], answer: null, note: 'Planner produced no sub-tasks.' }
}

// Execute is a genuine BARRIER before synthesis: the synthesizer needs the FULL
// set of findings at once, so parallel() (await-all) is correct here rather than
// a pipeline. Workers run cheap + low-effort in isolated contexts.
phase('Execute')
const findings = await parallel(
  subtasks.map((st, i) => () =>
    agent(workerPrompt(TASK, st), {
      label: `worker:${st.id || i}`,
      phase: 'Execute',
      model: WORKER_MODEL,
      effort: WORKER_EFFORT,
      schema: FINDING_SCHEMA,
    })
  )
)
const distilled = findings.filter(Boolean) // drop workers that errored/were skipped
if (distilled.length < subtasks.length) {
  log(`${subtasks.length - distilled.length} worker(s) produced no result — synthesizing from ${distilled.length}.`)
}

phase('Synthesize')
const answer = await agent(synthPrompt(TASK, distilled), {
  label: 'synthesizer',
  phase: 'Synthesize',
}) // synthesizer also inherits the strong session model; returns plain text

return {
  task: TASK,
  plan_summary: plan.plan_summary,
  subtaskCount: subtasks.length,
  workerModel: WORKER_MODEL,
  findings: distilled,
  answer,
}
