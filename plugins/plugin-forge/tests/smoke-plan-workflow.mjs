import assert from 'node:assert/strict'
import fs from 'node:fs/promises'

const workflowPath = process.argv[2]
if (!workflowPath) {
  throw new Error('Usage: node smoke-plan-workflow.mjs <workflow-path>')
}

const rawSource = await fs.readFile(workflowPath, 'utf8')
const source = rawSource.replace('export const meta =', 'const meta =')
assert.notEqual(source, rawSource, 'workflow export declaration was not found')

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const execute = new AsyncFunction('args', 'agent', 'phase', 'parallel', 'log', source)

const originalFetch = globalThis.fetch
globalThis.fetch = async () => {
  throw new Error('network access is forbidden in the workflow smoke test')
}

const makeParallel = () => async (thunks) =>
  Promise.all(
    thunks.map(async (thunk) => {
      try {
        return await thunk()
      } catch {
        return null
      }
    })
  )

try {
  const phases = []
  const calls = []
  const logs = []
  const agent = async (_prompt, options) => {
    calls.push(options)
    if (options.label === 'planner') {
      return {
        plan_summary: 'Split into two mocked units.',
        subtasks: [
          { id: 'one', title: 'First', instructions: 'Inspect the first fixture.' },
          { id: 'two', title: 'Second', instructions: 'Inspect the second fixture.' },
        ],
      }
    }
    if (options.label.startsWith('worker:')) {
      return {
        subtask_id: options.label.slice('worker:'.length),
        summary: 'Mocked worker result.',
        findings: ['fixture:1'],
        confidence: 'high',
        unresolved: [],
      }
    }
    if (options.label === 'verifier') {
      return {
        summary: 'Mocked findings are internally consistent.',
        checks: [{ claim: 'fixture', verdict: 'confirmed', note: 'fixture:1' }],
      }
    }
    if (options.label === 'synthesizer') return 'Mocked final answer.'
    throw new Error(`unexpected agent label: ${options.label}`)
  }

  const result = await execute(
    {
      task: 'Exercise the workflow without network access.',
      workerModel: 'mock-cheap',
      workerEffort: 'low',
      maxSubtasks: 4,
    },
    agent,
    (name) => phases.push(name),
    makeParallel(),
    (message) => logs.push(message)
  )

  assert.deepEqual(phases, ['Plan', 'Execute', 'Verify', 'Synthesize'])
  assert.equal(result.subtaskCount, 2)
  assert.equal(result.findings.length, 2)
  assert.equal(result.verification.checks[0].verdict, 'confirmed')
  assert.equal(result.answer, 'Mocked final answer.')
  assert.equal(
    calls.filter((call) => call.label.startsWith('worker:')).length,
    2
  )
  assert.ok(
    calls
      .filter((call) => call.label.startsWith('worker:') || call.label === 'verifier')
      .every((call) => call.model === 'mock-cheap' && call.effort === 'low')
  )
  assert.ok(logs.some((message) => message.includes('2 sub-task(s)')))

  const emptyPhases = []
  const emptyResult = await execute(
    'Exercise the empty-plan branch.',
    async (_prompt, options) => {
      assert.equal(options.label, 'planner')
      return { plan_summary: 'Nothing to delegate.', subtasks: [] }
    },
    (name) => emptyPhases.push(name),
    makeParallel(),
    () => {}
  )
  assert.deepEqual(emptyPhases, ['Plan'])
  assert.equal(emptyResult.subtaskCount, 0)
  assert.equal(emptyResult.answer, null)

  await assert.rejects(
    execute({}, async () => null, () => {}, makeParallel(), () => {}),
    /no task provided/
  )
} finally {
  globalThis.fetch = originalFetch
}

console.log('OK: plan-big-execute-small workflow smoke test passed with mocked agents')
