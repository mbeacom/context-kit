# runtime-evidence

!!! abstract "Controlled runtime evidence"
    Escalate an `unable-to-check` runtime claim only after static verification
    cannot settle it. Run one exact, pre-reviewed command ID for bounded
    artifacts — or an approved optional-tool observation when no reviewed
    command can represent the claim — and return the evidence record to `verify`
    for the verdict.

`runtime-evidence` depends on [`verify`](verify.md), which transitively pulls the
[`retrieval-core`](retrieval-core.md) spine. Prerequisites differ by path: the
bundled runner needs Python 3 (standard library only) on a POSIX platform and
refuses Windows before config access or process creation, while the
optional-tool path ships no runner and needs only an approved, host-exposed
observation tool.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install runtime-evidence@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install runtime-evidence@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install runtime-evidence@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`runtime-evidence`** skill | Static-verification escalation workflow for one unresolved runtime claim, covering both collection paths. |
| **`runtime-investigator`** subagent | Selects an existing reviewed command ID and returns verdict-ready evidence. Command-only. |
| **`/collect-runtime-evidence`** command | Starts a focused collection only after a static `unable-to-check` result. |
| **`run-evidence-command.py`** | Standard-library Python runner for exact allowlisted argv and bounded artifacts. |

## Two collection paths

| | Runner path | Optional-tool path |
| --- | --- | --- |
| When | a reviewed command ID reproduces the claim | no reviewed command can represent it |
| Runs in | the `runtime-investigator` subagent | the main agent |
| Bounded by | the allowlist, timeout, and output cap | operator approval plus host policy; nothing the plugin enforces — see [security](../security.md) |
| Observation source | `command-id=<allowlist key>` | `tool=<approved tool>@<target>` |
| Artifacts | runner-written report, stdout, stderr | at least one durable artifact, or the claim stays `unable-to-check` |

The plugin ships a runner for the first path only. For the second it supplies
approval conditions and a recording contract, not a mechanism: a subagent's tool
grant is fixed, so a host-exposed browser or debugger is reachable only from the
main agent. If the host exposes no suitable tool, that path is unavailable and
the claim stays unsettled.

## Exact-ID allowlist boundary

The JSON allowlist lives in a user-controlled location outside the installed
plugin. Each exact command ID maps to literal `argv`, a timeout of at most 300
seconds, and a per-stream byte cap of at most 1,048,576 bytes. The runner:

- performs no shell parsing, interpolation, globbing, substitution, or appended
  arguments;
- requires an explicit absolute working directory;
- checks config ownership and writable permissions where POSIX metadata exists;
- limits stdout and stderr independently and terminates the process group on
  timeout or overflow; and
- writes `<run-id>.stdout`, `<run-id>.stderr`, and `<run-id>.json` without
  overwriting existing artifacts.

Use `CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG` for the config,
`CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT` for the installed plugin root, and
`${CONTEXT_KIT_DATA}/runtime-evidence` for artifacts. Claude Code components may
use `CLAUDE_PLUGIN_ROOT` as the plugin-root fallback.

!!! warning "Selection is not side-effect proof"
    Allowlisting constrains which argv can be selected. It does **not** prove the
    executable is safe or side-effect-free: it may still mutate files, access
    credentials or networks, or start descendants. Host-level command policy is a
    separate layer; this plugin does not claim universal host-level enforcement.

## Returning evidence to verify

This plugin never assigns a verdict. It hands the collected facts back to
[`verify`](verify.md), which reassesses the *same* atomic claim under its
existing `confirmed` / `dubious` / `refuted` / `unable-to-check` taxonomy.

The returned verdict cites verify's observation evidence form — the observation
source plus an artifact pointer — rather than a repository `path:line`:

```text
evidence (command-id=health-cache-down; report=${CONTEXT_KIT_DATA}/runtime-evidence/run-4213.json)
evidence (tool=browser@https://staging.example/health; trace=${CONTEXT_KIT_DATA}/runtime-evidence/run-4219-trace.zip)
```

The first form is the sanctioned runner. The second covers an approved
optional-tool observation, allowed only when no reviewed command can represent
the claim.

Exit `0` means the configured process completed, not that the claim is true. A
timeout, output-cap termination, spawn failure, or an observation the claim does
not depend on leaves the verdict at `unable-to-check` with the limitation named.

## Integration boundary

The [continuity integration test](../ARCHITECTURE.md#tested-verification-to-continuity-boundary)
runs this real entry point, then explicitly compiles selected report provenance
into a handoff. Runtime reports are never ingested automatically.

## At a glance

| | |
| --- | --- |
| **Category** | verification |
| **Provides** | skill, command, subagent, stdlib Python runner |
| **Dependencies** | [`verify`](verify.md) → [`retrieval-core`](retrieval-core.md) |
| **License** | MIT |
