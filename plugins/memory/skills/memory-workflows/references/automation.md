# Opt-in Automation

The memory plugin declares `SessionStart`, `Stop`, `PreCompact`, and
`SessionEnd` hooks. Every one is inert until explicitly enabled, and they are
governed by **two independent switches**, because reading and writing are
different risks.

| Switch | Governs | Hook |
| --- | --- | --- |
| `CONTEXT_KIT_MEMORY_RECALL_ON_START` | injecting reviewed memory into a session | `SessionStart` |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | queuing lifecycle payloads for review | `Stop`, `PreCompact`, `SessionEnd` |

Both also require `CONTEXT_KIT_MEMORY_PROJECT`. A missing project is a visible
refusal, never a silent global fallback.

## Host boundaries

**Both Claude Code and GitHub Copilot CLI load a plugin's `hooks/hooks.json`**
and honor an `additionalContext` string returned on stdout. Verified
empirically against a live Copilot CLI install (1.0.79): plugin hooks appear in
the session event stream as `hook.start`/`hook.end` carrying `hookType`, and
Copilot bootstraps plugin data at
`~/.copilot/plugin-data/<marketplace>/<plugin>/`.

Copilot's internal `hookType` names are camelCase (`sessionStart`, `agentStop`,
`preCompact`, `sessionEnd`), but the `hooks.json` keys are the same PascalCase
names Claude uses, so one file serves both hosts.

APM does not deploy hooks, so on APM both paths stay explicit commands.

## Recall on session start

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_RECALL_ON_START=true
```

The hook emits the `wake` digest as `additionalContext`: a bounded, recency-
ordered list of **accepted and current** records only, capped by both a record
count and a character budget, because a priming block competes with real work
for context.

Recall is read-only, so it is deliberately not gated on `AUTO_CAPTURE`. If
anything fails — no project configured, an unreadable store — the hook prints
`{}` and the session proceeds. A memory problem must never break a session.

## Capture at boundaries

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

- Each hook writes the exact JSON payload to a mode-0600 file under
  `${CONTEXT_KIT_MEMORY_HOME}/pending-hooks/<project-key>/`.
- Queued payloads are unreviewed evidence. They are never searched, converted
  into `memory-v1` records, or written to a provider automatically.
- Review the payload, create a durable record, run explicit `capture`, then run
  `sync-provider --apply` if provider recall should change.
- Delete queued payloads under an operator-defined retention policy after
  review; they can contain sensitive session context.

The adapter does not evaluate shell text, install dependencies, or invoke a
provider from lifecycle hooks.

## Why not `PreToolUse` / `PostToolUse`

Both hosts expose tool-level hooks, and they are the wrong lifecycle point for
durable memory. Measured across a real Copilot session corpus:

| Hook | Invocations |
| --- | --- |
| `postToolUse` | 35,083 |
| `preToolUse` | 23,683 |
| `Stop` / `agentStop` | 1,040 |
| `sessionEnd` | 663 |
| `sessionStart` | 137 |
| `preCompact` | 121 |

Hooking tool calls would spawn a process per call — roughly 59,000 against
~1,800 for the boundaries — to capture per-tool noise rather than anything
durable. It would also amount to continuous transcript harvesting, which the
memory contract forbids. Memory hooks the boundaries where a unit of work
finishes, and nothing finer.

## Disable

```bash
unset CONTEXT_KIT_MEMORY_AUTO_CAPTURE
unset CONTEXT_KIT_MEMORY_RECALL_ON_START
```

Local reviewed records remain available; only the lifecycle behavior stops.
