# runtime-evidence

Controlled dynamic evidence collection for claims that static repository
verification cannot settle. The plugin turns a pre-reviewed command ID into
bounded stdout/stderr artifacts and a structured evidence record that can be
handed back to `verify` for a verdict.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install runtime-evidence@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install runtime-evidence@context-kit
```

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install runtime-evidence@context-kit
```

The plugin depends on `verify`; `verify` already pulls the `retrieval-core`
spine. The runner requires Python 3 on a POSIX platform. Windows receives a
structured refusal before the allowlist is read or a command is spawned.

## Components

| Component | Purpose |
| --- | --- |
| **`runtime-evidence`** skill | Escalates an `unable-to-check` runtime claim to a controlled observation, then returns the evidence to `verify`. |
| **`runtime-investigator`** agent | Selects an existing reviewed command ID, invokes only the sanctioned runner, and reports verdict-ready evidence. |
| **`/collect-runtime-evidence`** command | Starts a focused runtime investigation for one claim. |
| **`run-evidence-command.py`** script | Executes exact argv from a strict user-owned JSON allowlist without a shell, with required cwd and bounded runtime/output. |

## Quick start

Create a user-owned config outside the plugin:

```json
{
  "version": 1,
  "commands": {
    "api-health": {
      "argv": ["python3", "-m", "pytest", "-q", "tests/test_health.py"],
      "timeout_seconds": 60,
      "max_output_bytes": 65536
    }
  }
}
```

Then run an approved command ID:

```bash
python3 "${CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT}/scripts/run-evidence-command.py" \
  --config "${CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG}" \
  --command-id api-health \
  --claim "The health endpoint responds successfully" \
  --environment-label local-test \
  --cwd "$PWD" \
  --artifact-dir "${CONTEXT_KIT_DATA}/runtime-evidence" \
  --run-id api-health-001
```

For Claude Code, `${CLAUDE_PLUGIN_ROOT}` can replace
`${CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT}` inside plugin-provided commands.

## Safety boundary

The wrapper constrains **selection**, not behavior: it executes only the exact
argv registered under an exact command ID, never invokes a shell, requires an
explicit absolute cwd, and enforces configured timeout and per-stream output
limits. It also verifies that the config is owned by the current user and is not
group- or world-writable on platforms that expose POSIX ownership.

This does **not** prove an allowlisted command has no side effects. A reviewed
command can still mutate files, use credentials, access a network, or start child
processes. Host-level Bash restrictions are a separate permission layer and may
be broader or narrower than this wrapper. Review the config and command
implementation before use.

The runner never silently substitutes another command, cwd, config, or evidence
path. Browser and other host runtime tools are optional; unavailable tooling is
reported as a limitation rather than replaced with an unreviewed shell command.

See `skills/runtime-evidence/references/runner-contract.md` for the complete
config and exit-code contract.
