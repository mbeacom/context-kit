# context-handoff

Portable task-state handoffs for moving bounded, verified context between agent
sessions and hosts. The artifact records what is known, what changed, what
remains, and which repository state those claims were checked against.

This is not generic native session persistence. It does not serialize a chat,
restore hidden model state, install lifecycle hooks, or automatically ingest
handoffs into long-term RAG or memory. Manual commands remain authoritative.
The separate `memory` plugin can archive a validated handoff only when explicitly
requested; that copy is historical evidence and must be freshness-checked again
before resumption.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install context-handoff@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install context-handoff@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install context-handoff@context-kit
```

Installing `context-handoff` also installs `verify`, which supplies the
`verify-before-trust` discipline used to check handoff claims.

## Use

Write a handoff before leaving a task:

```text
/write-handoff
```

Resume from it in a later session:

```text
/resume-handoff
```

Both commands accept an optional artifact path. Without one, they use
`CONTEXT_KIT_HANDOFF_PATH`, then fall back to `.context-kit/handoff.md` relative
to the repository root.

## Components

| Component | What it is |
| --- | --- |
| **`context-handoff`** skill | The portable workflow and safety contract for compiling and resuming task state. |
| **`handoff-compiler`** subagent | A read-only compiler that returns bounded structured Markdown for the main agent to persist. |
| **`/write-handoff`** command | Gathers repository provenance, compiles verified task state, writes the artifact, and validates it. |
| **`/resume-handoff`** command | Validates structure and current repository identity before trusting the artifact, then rechecks stale claims. |
| **`scripts/validate-handoff.py`** | A standard-library validator with distinct invalid, mismatch, and stale exit statuses. |

For explicit historical retention after validation, install `memory` and run
`/archive-handoff`. This does not change the resume contract.

## Artifact contract

The `context-kit/handoff-v1` contract has explicit sections for:

- verified facts and their evidence;
- decisions and rationale;
- changed files;
- completed work;
- unresolved items and next steps;
- validation state;
- provenance and freshness, including repository, branch, base, HEAD, and
  worktree state.

Artifacts are limited to 32 KiB, 300 lines, and 25 top-level bullets per
section. See `skills/context-handoff/references/handoff-contract.md` for the
exact schema.

## Freshness behavior

Resume treats repository, branch, and base-ref differences as context
mismatches and rejects the handoff. HEAD, merge-base, or worktree-state
differences mark it stale; stale claims must be reverified before use. This
prevents a plausible-looking artifact from silently overriding current
repository evidence.

## Validate directly

```bash
python3 plugins/context-handoff/scripts/validate-handoff.py
```

Exit statuses are `0` for valid/current, `1` for malformed, `2` for a repository
identity mismatch, and `3` for stale state.
