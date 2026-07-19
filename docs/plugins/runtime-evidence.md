# runtime-evidence

!!! abstract "Controlled runtime evidence"
    Escalate an `unable-to-check` runtime claim only after static verification
    cannot settle it. Run one exact, pre-reviewed command ID and return bounded
    artifacts to `verify` for the verdict.

`runtime-evidence` depends on [`verify`](verify.md), which transitively pulls the
[`retrieval-core`](retrieval-core.md) spine. Python 3 is required; the runner uses
only the standard library and requires a POSIX platform. Windows is refused
before config access or process creation.

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
| **`runtime-evidence`** skill | Static-verification escalation workflow for one unresolved runtime claim. |
| **`runtime-investigator`** subagent | Selects an existing reviewed command ID and returns verdict-ready evidence. |
| **`/collect-runtime-evidence`** command | Starts a focused collection only after a static `unable-to-check` result. |
| **`run-evidence-command.py`** | Standard-library Python runner for exact allowlisted argv and bounded artifacts. |

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
