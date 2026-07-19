---
name: runtime-evidence
description: "Use when static verification cannot settle a claim about actual runtime behavior and controlled dynamic evidence is needed from a user-supplied, pre-reviewed command ID."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash
---

# Runtime Evidence

Collect dynamic evidence only after static verification reaches
`unable-to-check` for a runtime claim. Keep verdict assignment in `verify`;
produce a controlled observation package that lets the verifier confirm, refute,
qualify, or retain that verdict.

Treat execution as an escalation, not a default search technique. Prefer code,
config, tests, and other static primary evidence when those sources settle the
claim.

## Evidence flow

1. State one atomic runtime claim and preserve the static verification result
   that explains why execution is necessary.
2. Identify the environment whose behavior matters. Record a concise label and
   the explicit absolute working directory.
3. Inspect the user-owned allowlist config. Select an exact existing command ID
   whose reviewed argv reproduces the claim.
4. Refuse to proceed when no reviewed command ID matches. Never invent an ID,
   alter argv in memory, edit the config, or substitute direct shell execution.
5. Invoke `scripts/run-evidence-command.py` with the config, command ID, claim,
   environment label, cwd, artifact directory, and unique run ID.
6. Preserve the runner's exit status and JSON report. Treat timeout, output-limit
   termination, spawn failure, and child nonzero exit as observations rather
   than smoothing them into success.
7. Return the report to `verify` for the verdict. Do not create a parallel verdict
   taxonomy or a bespoke Plan -> Execute -> Verify -> Synthesize workflow.

## Sanctioned execution path

Use the deterministic wrapper as the default path:

```bash
python3 "${CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT}/scripts/run-evidence-command.py" \
  --config "${CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG}" \
  --command-id "<reviewed-id>" \
  --claim "<atomic runtime claim>" \
  --environment-label "<environment>" \
  --cwd "<absolute working directory>" \
  --artifact-dir "${CONTEXT_KIT_DATA}/runtime-evidence" \
  --run-id "<unique-run-id>"
```

Inside Claude Code plugin components, use
`${CLAUDE_PLUGIN_ROOT}/scripts/run-evidence-command.py` when the neutral plugin
root variable is not available. Prefer `CONTEXT_KIT_*` variables in portable
instructions.

The wrapper passes configured argv directly to the operating system without a
shell. It enforces a config-defined timeout and per-stream output cap, refuses
unknown command IDs, refuses unsafe config ownership/permissions where POSIX
metadata is available, and requires explicit locations instead of guessing.

## Safety rules

- Require commands to be supplied and reviewed by the user or repository owner
  before execution.
- Treat the allowlist as a command-selection boundary, not a side-effect proof.
  An allowlisted executable can still mutate state, access credentials, use the
  network, or spawn descendants.
- Keep host-level Bash permission separate from wrapper policy. A host may allow
  broad Bash while the wrapper permits one command ID, or may block the wrapper
  despite a valid config.
- Never reinterpret command strings, append flags, interpolate claim text into
  argv, or invoke `sh`, `bash`, `eval`, or another command as a fallback.
- Never hide failure. Preserve wrapper and child exit codes and include
  limitations and cleanup status in the handoff.

## Optional runtime tools

Use a browser, debugger, container inspector, or host-specific runtime tool only
when the user has approved that observation path and the host exposes the tool.
When it is unavailable, report the missing capability and leave the claim
unsettled. Do not replace it with a newly invented command.

## Output contract

Return these fields for every attempted collection:

- **Claim** — the atomic runtime statement under test.
- **Reproduction command ID** — the exact allowlist key; never a reconstructed
  command string.
- **Environment** — label, cwd, platform, and interpreter metadata from the
  runner report.
- **Observations** — exit code, termination reason, bounded stdout/stderr
  excerpts, byte counts, and truncation flags.
- **Artifact/output pointers** — report, stdout, stderr, and config digest/path.
- **Verdict-ready evidence** — concise facts suitable for the `verify` verdict
  taxonomy without assigning a new taxonomy here.
- **Limitations** — side-effect uncertainty, missing tools, environment gaps,
  output truncation, timeout, or other constraints.
- **Cleanup status** — whether no cleanup was needed or the process group was
  terminated; never imply command side effects were reversed.

Read `references/evidence-report.md` before formatting a handoff.

## Composition

Use `verify` first and last: static verification identifies the runtime gap, and
its verifier consumes the resulting evidence. Apply `retrieval-strategy` through
that dependency when locating static evidence is difficult.

Optionally use `plan-execute` to partition many independent claims before
collection. Keep every execution unit bound to an existing allowlist command ID;
orchestration never expands execution authority.

## References

- **`references/runner-contract.md`** - Strict config schema, invocation,
  ownership checks, artifacts, and exit codes.
- **`references/evidence-report.md`** - Required verdict-ready handoff shape.
- **`references/optional-tools.md`** - Graceful degradation for browser and
  host-specific runtime tools.
