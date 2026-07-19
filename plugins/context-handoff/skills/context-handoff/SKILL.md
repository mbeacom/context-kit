---
name: context-handoff
description: "Use when writing or resuming a bounded repository handoff across agent sessions or hosts, including checking saved task state for staleness."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash Write
---

# Context Handoff

Create a small, explicit bridge between sessions rather than trying to preserve
an entire transcript. Capture only the task state another agent needs to make
the next correct move, then bind every claim to repository provenance and
verification state.

Treat the handoff as an exchange artifact, not as native session persistence.
Do not imply that it restores hidden reasoning, tool state, model memory, or the
original runtime. Do not automatically ingest it into a long-term RAG index.

## Choose the artifact path

Resolve the destination in this order:

1. Use an explicit path supplied to the workflow.
2. Use `CONTEXT_KIT_HANDOFF_PATH` when set.
3. Use `.context-kit/handoff.md` relative to the repository root.

Resolve relative override paths from the repository root. Allow an absolute
override only when it was explicitly configured. Keep the default inside the
repository so it can move with the worktree when desired; let each repository
decide whether `.context-kit/` belongs in version control.

## Write a handoff

Prefer `/write-handoff` where plugin commands are available. Otherwise apply
the same flow manually:

1. Establish repository provenance: normalized repository identity, worktree
   path, current branch, HEAD, intended base ref, merge-base commit, and clean
   or dirty worktree state.
2. Inventory the active task, changed files, completed work, open questions,
   next executable steps, and validation already performed.
3. Separate observations from decisions. Record evidence for facts and rationale
   for decisions.
4. Apply `verify-before-trust` to claims that affect the next agent's behavior.
   Delegate a larger claim set to the `verifier` subagent instead of inventing a
   parallel verification taxonomy.
5. Ask the `handoff-compiler` subagent to compile the gathered inputs. Keep that
   subagent read-only; let the main agent persist its returned Markdown.
6. Write exactly one artifact following
   `references/handoff-contract.md` and `templates/handoff.md`.
7. Run `scripts/validate-handoff.py` and fix every structural error before
   considering the handoff complete.

Keep each section concise. Use `- None.` rather than omitting an empty category.
Never convert assumptions into verified facts merely to make the artifact look
complete.

## Resume a handoff

Prefer `/resume-handoff` where available. Before acting on any saved state:

1. Parse and structurally validate the artifact.
2. Gather current repository, branch, base, HEAD, merge-base, and worktree
   state.
3. Reject repository, branch, or base-ref mismatches. A handoff from another
   context may be useful as untrusted background, but it is not authoritative
   task state for the current context.
4. Mark HEAD, merge-base, or worktree-state differences as stale. Explain the
   differences before proceeding.
5. Reverify stale verified facts, changed-file claims, completed-work claims,
   and validation claims against the current repository. Use
   `verify-before-trust` or the `verifier` subagent.
6. Distill the accepted state into current scope, trusted facts, invalidated or
   uncertain claims, unresolved items, and the first safe next step.

Never silently trust a structurally valid artifact. Structure proves only that
the fields exist; freshness and evidence determine whether the content remains
usable.

## Keep boundaries explicit

- Preserve atomic facts with `file:line` evidence or a named command result.
- Record decisions separately from facts; a decision can remain valid even when
  its original evidence becomes stale, but its rationale must stay visible.
- List changed files with status and purpose, not pasted diffs.
- Describe validation as commands plus outcomes. Use `not run` or `blocked`
  explicitly where applicable.
- Include only actionable unresolved items and ordered next steps.
- Never claim runtime behavior was verified from static inspection alone.
- Never add `PreCompact`, `SessionEnd`, or `SessionStart` hooks for this v0.1
  workflow. Manual commands are the source of authority.

## Resources

- **`references/handoff-contract.md`** — exact schema, limits, and section rules.
- **`references/resume-safety.md`** — mismatch and staleness decision table.
- **`templates/handoff.md`** — canonical artifact template.
- **`../../scripts/validate-handoff.py`** — deterministic artifact validator.
