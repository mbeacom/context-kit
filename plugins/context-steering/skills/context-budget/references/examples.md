# Worked Examples

Use these scenarios as placement tests: if the wrong layer is tempting, ask what should actually trigger the guidance.

## Scenario 1: Format TypeScript after edits

- Guidance: Run Prettier after editing TypeScript or TSX files.
- Wrong layer: Always-on memory that says "remember to run Prettier."
- Right layer: A `PostToolUse` hook, such as [`format-on-edit.post-tool-use.json`](../../../examples/hooks/format-on-edit.post-tool-use.json).
- Why: Formatting is deterministic. A hook reacts to edits without spending tokens or relying on recall.

## Scenario 2: Validate backend API input

- Guidance: API handlers under `src/api/**` must validate request bodies with Zod before business logic runs.
- Wrong layer: A global `CLAUDE.md` / `AGENTS.md` paragraph seen on every task.
- Right layer: A path-scoped rule, adapted from [`backend-api.md`](../../../examples/rules/backend-api.md).
- Why: The convention matters only when the agent touches that area.

## Scenario 3: Perform a full security review

- Guidance: Use a multi-step review covering threat model, auth boundaries, input validation, data exposure, dependency risk, and exploitability.
- Wrong layer: A huge always-on checklist.
- Right layer: A skill with a precise description and deeper `references/` files.
- Why: The review method is large and valuable, but it is occasional. Load it only when the task asks for security review depth.

## Scenario 4: Audit 40 files for a migration pattern

- Guidance: Inspect many files for a repeated pattern and summarize the affected call sites.
- Wrong layer: A skill body that tries to hold every intermediate finding in the main conversation.
- Right layer: One or more delegated subagents with narrow file ranges or independent packages.
- Why: The work is isolatable and context-heavy. Subagents keep scratch context out of the main thread and can run in parallel.

## Scenario 5: Block obvious secrets in writes

- Guidance: Prevent writes that contain obvious access keys or `password =` assignments.
- Wrong layer: A memory rule asking the model not to write secrets.
- Right layer: A `PreToolUse` hook, such as [`block-secrets.pre-tool-use.json`](../../../examples/hooks/block-secrets.pre-tool-use.json).
- Why: Secret blocking must be deterministic and fail closed before the write lands.
