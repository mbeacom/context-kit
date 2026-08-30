# Opt-in Automation

The memory plugin declares `SessionStart`, `Stop`, `PreCompact`, and
`SessionEnd` hooks. Memory recall and payload queuing are inert until explicitly
enabled and are governed by **two independent switches**, because reading and
writing are different risks.

| Switch | Governs | Hook |
| --- | --- | --- |
| `CONTEXT_KIT_MEMORY_RECALL_ON_START` | injecting reviewed memory into a session | `SessionStart` |
| `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` | queuing lifecycle payloads for review | `Stop`, `PreCompact`, `SessionEnd` |

Both also require a project scope. Explicit configuration is portable and always
wins. GitHub Copilot Desktop can supply the scope through the trusted ephemeral
session binding described below; all other hosts require
`CONTEXT_KIT_MEMORY_PROJECT` (or the documented fallback).

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

### Bounded Copilot routing metadata

GitHub Copilot Desktop has no clean per-project environment surface for a
plugin-contributed MCP server. Its host-authored `SessionStart` input does carry
`cwd` and `sessionId`, while the MCP child receives
`COPILOT_AGENT_SESSION_ID`. The provider uses that pair only when:

1. `COPILOT_AGENT_SESSION_ID` is present and is a safe filename component;
2. payload `sessionId` exactly matches it;
3. payload `cwd` is absolute and resolves through `git rev-parse
   --show-toplevel`; and
4. that repository has an `origin` that normalizes to `owner/repository`.

No MCP working directory, `PWD`, prompt content, or model-supplied tool argument
participates. Missing, invalid, originless, or conflicting context leaves memory
unbound.

The hook writes only `session_id` and normalized `project` under
`${CONTEXT_KIT_MEMORY_HOME}/session-bindings/`: the directory is mode 0700 and
each atomic write-once JSON file is mode 0600. Repeating `SessionStart` for the
same session/project is idempotent; reusing that session ID for another project
is refused. A matching `SessionEnd` removes the binding. `Stop`/`agentStop` does
not. A crash may leave a file, but unique host session IDs prevent another
session from resolving it.

This is ephemeral routing metadata, not a `memory-v1` record, lifecycle payload,
provider projection, or permission to retain session content. Explicit
`--project`, portable/legacy project environment variables, and Claude's plugin
option all take precedence over it. APM and hosts without the matching Copilot
hook plus session environment must configure a project explicitly.

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
anything fails — no project scope, an unreadable store — the hook prints
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
Copilot's minimal session routing binding is still created and cleaned because
it is neither recall nor capture.
