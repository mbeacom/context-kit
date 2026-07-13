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
//   Verify     — one CHEAP agent independently re-checks the workers' claims,
//                read-only, so the synthesizer never grades its own inputs.
//   Synthesize — one STRONG agent merges the verified findings into the answer.
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
    'Strong planner decomposes a task; cheap workers execute the sub-tasks in parallel; a cheap agent verifies their claims; a strong synthesizer merges.',
  whenToUse:
    'Token-heavy coverage work that splits into independent sub-tasks — multi-file audits, broad research sweeps, large log/document reviews — where planning + synthesis want a strong model but the reading is mechanical.',
  phases: [
    { title: 'Plan', detail: 'Strong model decomposes the task into independent sub-tasks' },
    { title: 'Execute', detail: 'Cheap workers each handle one sub-task in an isolated context' },
    { title: 'Verify', detail: 'A cheap agent independently re-checks worker claims, read-only' },
    { title: 'Synthesize', detail: 'Strong model merges the verified findings into the answer' },
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

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['summary', 'checks'],
  properties: {
    summary: { type: 'string', description: 'One or two sentences on the overall reliability of the findings.' },
    checks: {
      type: 'array',
      description: 'One entry per material claim that was independently re-checked.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'verdict'],
        properties: {
          claim: { type: 'string', description: 'The worker claim being checked (quote or paraphrase).' },
          verdict: { type: 'string', enum: ['confirmed', 'dubious', 'refuted', 'unable-to-check'] },
          note: { type: 'string', description: 'One line: what you re-checked and what you saw, with a source pointer.' },
        },
      },
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

const verifyPrompt = (task, distilled) => `You are an independent VERIFIER. Do NOT trust the workers' claims, and do NOT modify anything — re-check, read-only.

OVERALL TASK:
${task}

WORKER FINDINGS (JSON):
${JSON.stringify(distilled, null, 2)}

Independently re-check the material claims: re-open the cited file:line, re-run any
verification the task names, and confirm each claim actually holds. Never accept a
"passed" / "works" / "done" assertion without checking it yourself. For each material
claim return a verdict — confirmed / dubious / refuted / unable-to-check — with a
one-line note and a source pointer. You report problems; you do not fix them. Return
the structured output.`

const synthPrompt = (task, distilled, verdicts) => `You are the SYNTHESIZER in a plan-big / execute-small pipeline.
The token-heavy reading is done; ${distilled.length} worker(s) reported distilled findings below, and an independent verifier re-checked them.

OVERALL TASK:
${task}

WORKER FINDINGS (JSON):
${JSON.stringify(distilled, null, 2)}

INDEPENDENT VERIFICATION (JSON):
${JSON.stringify(verdicts, null, 2)}

Merge the findings into a single, coherent answer to the task. Weigh the verification:
treat any claim marked "refuted" or "dubious" with skepticism and do NOT present it as
established — flag it or drop it. Resolve overlaps and contradictions (prefer
higher-confidence, better-cited, verified findings, and surface genuine conflicts
rather than hiding them). Carry file:line / source pointers through into your answer,
and call out anything still unresolved or unverifiable. Do not re-read source material —
synthesize only from the findings, the verification, and the task.`

// ---- pipeline ---------------------------------------------------------------

phase('Plan')
const plan = await agent(plannerPrompt(TASK), {
  label: 'planner',
  phase: 'Plan',
  schema: PLAN_SCHEMA,
}) // planner inherits the (strong) session model — do NOT override it

// Guard the shape: the schema should force `subtasks` to an array, but a planner
// that dies (agent() -> null) or returns a malformed object must not crash the run.
const planned = plan && Array.isArray(plan.subtasks) ? plan.subtasks : []
const subtasks = planned.slice(0, MAX_SUBTASKS)
if (planned.length > MAX_SUBTASKS) {
  log(`Planner returned ${planned.length} sub-tasks; capping at ${MAX_SUBTASKS}.`)
}
log(`Plan: ${plan ? plan.plan_summary : '(planner returned nothing)'} — ${subtasks.length} sub-task(s)`)

if (subtasks.length === 0) {
  return { task: TASK, plan, subtaskCount: 0, findings: [], answer: null, note: 'Planner produced no sub-tasks.' }
}

// Execute is a genuine BARRIER before verification/synthesis: those steps need the
// FULL set of findings at once, so parallel() (await-all) is correct here rather
// than a pipeline. Workers run cheap + low-effort in isolated contexts.
//
// No per-worker try/catch is needed: parallel() resolves a thunk that throws (or
// whose agent hits a terminal error) to null, so one worker failing never aborts
// the run — the filter(Boolean) below drops the nulls and we synthesize from the
// survivors (and bail entirely if none survive).
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
  log(`${subtasks.length - distilled.length} worker(s) produced no result — continuing with ${distilled.length}.`)
}

// Every worker failed: skip the (expensive, strong-model) synthesizer rather than
// paying it to summarize an empty finding set.
if (distilled.length === 0) {
  log('All workers failed to produce findings — skipping verification and synthesis.')
  return {
    task: TASK,
    plan_summary: plan.plan_summary,
    subtaskCount: subtasks.length,
    workerModel: WORKER_MODEL,
    findings: [],
    answer: null,
    note: 'All workers failed to produce findings; synthesis skipped.',
  }
}

// Verify is a BARRIER too: an independent cheap agent re-checks the workers' claims
// (read-only) so the strong synthesizer isn't left grading its own inputs. Refuted /
// dubious claims are surfaced to synthesis rather than silently trusted. If the
// verifier itself dies, we degrade gracefully to synthesizing unverified findings.
phase('Verify')
const verdicts = await agent(verifyPrompt(TASK, distilled), {
  label: 'verifier',
  phase: 'Verify',
  model: WORKER_MODEL,
  effort: WORKER_EFFORT,
  schema: VERIFY_SCHEMA,
})
if (!verdicts) log('Verifier produced no result — synthesizing from unverified findings.')

phase('Synthesize')
const answer = await agent(synthPrompt(TASK, distilled, verdicts), {
  label: 'synthesizer',
  phase: 'Synthesize',
}) // synthesizer also inherits the strong session model; returns plain text

return {
  task: TASK,
  plan_summary: plan.plan_summary,
  subtaskCount: subtasks.length,
  workerModel: WORKER_MODEL,
  findings: distilled,
  verification: verdicts,
  answer,
}
