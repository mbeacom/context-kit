# Runner Contract

## Configuration

Store the JSON config in a user-controlled location, not inside the installed
plugin. The root object accepts exactly `version` and `commands`:

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

Each command entry requires exactly:

- `argv`: a non-empty array of literal strings. The runner performs no shell
  parsing, interpolation, globbing, substitution, or argument extension.
- `timeout_seconds`: a positive number no greater than 300.
- `max_output_bytes`: a positive integer no greater than 1,048,576. The cap
  applies independently to stdout and stderr.

Command IDs must match `[a-z0-9][a-z0-9._-]{0,63}`. Unknown fields are refused so
misspelled policy does not disappear silently.

On POSIX systems, the resolved config file must be owned by the current effective
user and must not be writable by group or others. This ownership check establishes
who controls command selection; it does not audit the selected executable.

## Required invocation inputs

Provide all of the following:

```text
--config PATH
--command-id ID
--claim TEXT
--environment-label TEXT
--cwd ABSOLUTE_DIRECTORY
--artifact-dir DIRECTORY
--run-id ID
```

`--config` may come from `CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG`, and
`--artifact-dir` may resolve to
`${CONTEXT_KIT_DATA}/runtime-evidence`. If neither an argument nor its documented
environment variable is present, the runner refuses to execute. `--cwd` is always
explicit and absolute.

The neutral plugin-root convention is
`CONTEXT_KIT_RUNTIME_EVIDENCE_ROOT`. Claude Code components can use
`CLAUDE_PLUGIN_ROOT` as the host-provided fallback.

## Artifact behavior

The artifact directory receives three files:

```text
<run-id>.stdout
<run-id>.stderr
<run-id>.json
```

The runner refuses to overwrite any of them. Stdout and stderr artifacts contain
at most the configured bytes. The JSON report points to all three files and to
the resolved config path plus its SHA-256 digest.

The runner itself prints the JSON report to stdout after writing it. Child output
is never mixed into runner stdout.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Child command completed successfully. |
| `2` | Invocation, config, ownership, command-ID, cwd, or artifact refusal. No command ran. |
| `124` | Timeout reached; the runner terminated the process group. |
| `125` | Stdout or stderr exceeded its cap; the runner terminated the process group. |
| `126` | Configured command could not be spawned. |
| other | Child nonzero exit code, propagated unchanged. A signal is normalized to `128 + signal`. |

Every post-spawn outcome produces a report, including timeout, output-limit
termination, spawn failure, and child nonzero exit.

## Security boundary

The wrapper constrains which reviewed argv may be selected. It cannot establish
that argv is safe or side-effect-free. Review executable behavior, credentials,
network access, filesystem access, descendant processes, and cleanup needs
before adding an entry.

Host Bash policy remains independent. Granting the wrapper in a host does not
grant arbitrary Bash through the wrapper; granting broad Bash in a host does not
make direct shell execution part of this skill's sanctioned path.
