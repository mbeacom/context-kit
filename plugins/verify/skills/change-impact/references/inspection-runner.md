# Inspection Runner Contract

The `change-impact` skill ships an enforced read-only executor at
`scripts/run-impact-inspection.py`. It exists so a caller can reach the history,
structured-data, structural, and governance modalities under an actually-enforced
non-mutating constraint, instead of relying on a delegate's instructions or a
prefix-matched command grant that still admits write and exec vectors.

## Platform support

Run the runner with Python 3 on a POSIX platform. Like the `runtime-evidence`
runner, it uses selector-backed non-blocking pipe capture and process-group
termination that do not port to Windows. `main()` validates the platform before
anything is spawned and, on a non-POSIX host, exits `2` with a machine-readable
refusal rather than pretending to enforce a boundary it cannot.

## The catalog is plugin-owned, not operator-supplied

This is the deliberate difference from `runtime-evidence`. There, an operator
reviews a JSON allowlist and the runner trusts that review. Here, the runner
ships its own fixed catalog of inspection operations in code. The read-only
property is therefore a property of the shipped code, not of a per-site review:
the runner builds every argv itself from a fixed template, and the only thing a
caller supplies is a set of validated parameters. There is no config file to
audit and no way to add an operation without changing the plugin.

An allowlist of permitted argument *shapes* per operation is the mechanism, not
a denylist of bad flags. A denylist is a losing game — new tool releases add new
write and exec flags, and a scoped prefix grant still matches them. Because the
runner never accepts a raw flag or expression and never runs a shell, a value
that looks like `--output=…`, `--open-files-in-pager=…`, `-i`, or `-c core.pager=…`
is inert: it can only land in a parameter slot that validates it, and a slot that
would accept it does not exist.

## Discovery

```text
run-impact-inspection.py --list
```

`--list` prints the JSON catalog — every operation ID, its modality, the tool it
needs, its summary, and its parameter schema — then exits `0`. Agents and the
skill doc should read the catalog rather than hardcode operation IDs, so the two
cannot drift.

## Invocation

```text
run-impact-inspection.py --operation ID --root ABSOLUTE_DIR [--param name=value ...]
                         [--timeout-seconds N] [--max-output-bytes N]
```

- `--operation` must be a catalog ID. An unknown ID is refused, never guessed.
- `--root` is the analysis root. It may come from `CONTEXT_KIT_IMPACT_ROOT`. It
  must be an existing absolute directory; the runner resolves it and confines
  every path parameter inside it. The neutral plugin-root convention for the
  script's own location is `CONTEXT_KIT_VERIFY_ROOT`; Claude Code components can
  use `${CLAUDE_PLUGIN_ROOT}` as the host-provided fallback.
- `--param name=value` is repeatable. Each parameter is validated by kind and
  positionally substituted into the operation's argv; it is never concatenated
  into a flag string.
- `--timeout-seconds` and `--max-output-bytes` are clamped to the runner's
  ceilings (120 s, 1,048,576 bytes) and default to 30 s and 262,144 bytes.

## Parameter kinds

| Kind | Accepts | Placed as |
| --- | --- | --- |
| `count` | integer `1`–`10000` | `--max-count=<n>` (built by the runner) |
| `rev` | `[A-Za-z0-9][A-Za-z0-9._/~^-]*`, no leading dash | a positional revision |
| `pattern` | non-empty, NUL-free text, read as a basic regular expression | the argument of `git grep --basic-regexp -e` |
| `field` | dotted `[A-Za-z0-9_-]` segments | a `jq`/`yq` bracket filter `.["a"]["b"]`, assembled by the runner — never a raw expression |
| `path` | repo-relative, no leading dash | a positional after `--`, confined inside `--root` |

A `path` is rejected if it is absolute, begins with a dash, or — after symlink
resolution — falls outside the resolved root. A `rev` or `field` that could carry
a flag or a raw query is rejected before anything spawns.

A `field` is not concatenated into a dotted filter: each accepted segment is
JSON-encoded into a bracket key, so `a.b` becomes `.["a"]["b"]`. A bare dotted
filter would be unsafe for both `jq` and `yq` — `.release-name` parses as
subtraction (`.release` minus `name`) and a digit-leading `.2fa` is a syntax
error — so the bracket form is what guarantees every accepted segment addresses
the literal key it names. The encoding uses `json.dumps`, so it stays correct if
the accepted character set is ever widened.

## Operation catalog

Every git operation is built through one helper, so the runner-owned hardening
cannot drift between operations. Each git argv is prefixed with
`git -c core.fsmonitor= -c core.pager=cat --no-pager` and carries `--no-color`;
the diff-producing operations additionally carry `--no-ext-diff --no-textconv`.
The `Runs` column below shows the operation-specific tail after that shared
prefix.

| ID | Modality | Tool | Runs (after the shared git prefix) |
| --- | --- | --- | --- |
| `git-log-path` | history | git | `log --no-color --max-count=<count> -- <path>` |
| `git-log-recent` | history | git | `log --no-color --oneline --max-count=<count>` |
| `git-show-commit` | history | git | `show --no-color --no-ext-diff --no-textconv --stat <rev>` |
| `git-diff-revs` | history | git | `diff --no-color --no-ext-diff --no-textconv <base> <head> [-- <path>]` |
| `git-blame-path` | history | git | `blame --no-color --no-textconv -- <path>` |
| `git-grep` | structural | git | `grep -n --no-color --basic-regexp -e <pattern> [-- <path>]` |
| `json-keys` | structured-data | jq | `jq --sort-keys keys <path>` |
| `json-field` | structured-data | jq | `jq '.["a"]["b"]' <path>` (bracket filter from `<field>`) |
| `json-paths` | structured-data | jq | `jq -c paths <path>` |
| `json-type` | structured-data | jq | `jq type <path>` |
| `yaml-keys` | structured-data | yq | `yq keys <path>` (mikefarah yq) |
| `yaml-field` | structured-data | yq | `yq '.["a"]["b"]' <path>` (mikefarah yq, bracket filter) |
| `adr-explain-path` | governance | adr | `adr explain <path> --dir <dir> --json` |
| `adr-check-path` | governance | adr | `adr check <path> --dir <dir> --json` |

Every git argv carries `--no-pager` and `--no-color` as fixed literals, closing
the pager-exec vector before a parameter is even considered. The shared prefix
also pins the program-executing repository-local config surfaces (see
*Environment hardening*): `core.pager` and `core.fsmonitor` via `-c`, and
`diff.external`/textconv diff drivers via `--no-ext-diff`/`--no-textconv` on the
operations that can invoke a diff driver.

`git-grep` additionally carries `--basic-regexp` so the documented pattern kind
is enforced by the runner, not left to the repository. `git grep` otherwise
honors the repository-local `grep.patternType` config — which
`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` do not reach — so a repo set to
`extended`, `perl`, or `fixed` would silently change what the `pattern` parameter
means. The fixed flag overrides that config, the same class of gap already closed
for `core.fsmonitor` and `diff.external`.

## Governance: what decisions already bind this path

The other modalities answer what the code *is* and how it *got that way*. The
governance modality answers a question they cannot: what the team already
**decided** about this path, including the options it rejected.

That matters for impact analysis specifically. A change can be structurally
sound, historically unremarkable, and still wrong because it re-opens a settled
decision or violates a constraint recorded when the tradeoff was last examined.
Nothing in `git log` says "we considered this and ruled it out."

`adr-explain-path` returns the governing records with their status, the matchers
that fired, and — for records a file declares inline via an `@adr NNNN` comment —
the declaring line. Superseded and rejected decisions are reported too, which is
the point: it is how an agent stops re-proposing a path the team already closed.

Two properties make this safe to enforce here rather than merely suggest:

- **Read-only by construction.** Only `explain` and `check` appear in the
  catalog. adrkit's writing verbs (`new`, `migrate`) are absent, and a test
  asserts they stay absent. adrkit's own MCP surface makes the same guarantee —
  no model calls, no sockets, no corpus mutation.
- **Optional, and honest about it.** adrkit is contributor-side and not a
  dependency of anything shipped (ADR-0003). When `adr` cannot be resolved the
  runner exits `3` / `unavailable`, and the modality must be reported as
  unreached. A corpus that does not exist is not evidence that no decision
  governs the path.

### Reaching adrkit

`unavailable` is the correct result when the tool is absent, but on its own it is
inert — it is indistinguishable from a modality nobody wanted, so an install that
was never done is never noticed. Two things close that gap.

The `unavailable` payload names the remedy verbatim, and `CONTEXT_KIT_ADR_BIN`
lets an operator point at an install that is not a bare `adr` on `PATH`:

```bash
npm i -g @adrkit/cli@0.13.0                     # provides `adr`
# or, without a global install:
export CONTEXT_KIT_ADR_BIN=./node_modules/.bin/adr
```

The variable must name an executable that **already exists**; a package
specifier is refused, not fetched. A value that is set but unusable is a refusal
(exit `2`), never a quiet fallback to `PATH` — falling back would run a different
binary than the operator named and hide the misconfiguration. That includes a
variable set to nothing: absent and blank are different states, and reading a
blank value as "unset" would silently resolve a different binary than the one
configured. Unset it to resolve on `PATH`.

This does not widen the trust boundary. The runner already forwards the ambient
`PATH` to the child, so anyone who can set this variable can already decide what
`adr` resolves to; the variable is that same authority stated explicitly.

**An `npx` fallback was considered and rejected.** It is the obvious fix — the
repository documents adrkit through `npx` — but `npx --yes` contacts the npm
registry on *every* invocation, even with a pinned version and a warm cache.
Adding it would falsify the "read-only, offline" contract these two operations
advertise, turn a runner whose entire property is executing operator-installed
binaries from a fixed catalog into one that downloads and executes registry code
mid-analysis, and surface a network failure as npm's exit code rather than as
`unavailable` — breaking the unreached contract exactly when the network is
degraded. Naming a binary the operator already installed keeps every one of those
properties; fetching one does not.

The corpus directory defaults to `docs/adr` and is a normal path parameter, so
it is subject to the same containment check as any other path.

### When this modality earns its keep — and when it does not

Governance is the modality most likely to return a confident-looking result that
adds nothing. Calibrate it before quoting it.

- **A citation is not a finding.** Ask whether the record *changes* the
  conclusion. If the constraint is already restated in always-on context
  (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`) or enforced by a
  CI gate, the record adds provenance, not information — the analysis would have
  reached the same answer without it. Governance pays when the corpus holds what
  those files cannot: the *rejected* options, the tradeoff as examined at the
  time, and the revisit condition.
- **Check the status distribution.** The headline claim — that this stops an
  agent re-proposing a closed path — depends on the corpus actually holding
  `rejected` and `superseded` records. A corpus where every record is `accepted`
  has not yet exercised that value; it is doing pattern-matched attribution.
- **`governedBy` is only as good as `affects`.** The matchers decide everything.
  Measure them: if nearly every path matches nearly every record, the modality
  returns noise; if a path matches nothing, that is silence, not absolution.
- **Empty `declared` is not "no decision declared".** Inline `@adr` markers are
  scanned only within a bounded window from the start of the file (8192 bytes in
  adrkit 0.4.0), and a marker past it is dropped with no distinguishing signal —
  `markers.truncated` reports that the file exceeds the window, and is `true`
  even when a marker *was* found. Markers are a header convention; treat their
  absence in a large file as indeterminate.
- **A corpus nobody points at is never queried.** Retrievability is upstream of
  value. If nothing in the always-on instruction files names the corpus, no
  analysis reaches this modality in the first place, and that silence is
  indistinguishable from a corpus with nothing to say — the same failure shape as
  an absent binary yielding an inert `unavailable`. A pointer is enough, and is
  not the same as restating the rules there, which would spend the fixed budget
  to duplicate what the corpus exists to hold.
- **Given that pointer, it scales where instruction files cannot.** Always-on
  context is a fixed budget; a decision corpus is not. The case for retrieving
  governance grows with the number of records, and is weakest on a small corpus
  whose rules already fit in the instruction files.

## Environment hardening

The child runs with a minimal environment built from scratch — only `PATH` and
`LANG`/`LC_ALL=C` are carried over. Every inherited `GIT_*` redirection variable
(`GIT_DIR`, `GIT_WORK_TREE`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`, `GIT_SSH*`,
`GIT_CONFIG*`, and the rest) is dropped by construction, because the environment
is an allowlist rather than a filtered copy. `HOME` is deliberately not
forwarded, so a per-user rc file a tool would otherwise autoload — `~/.gitconfig`,
`~/.jq` — is unreachable as well. The runner then pins:

- `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` to the null device, plus
  `GIT_CONFIG_NOSYSTEM=1`. This neutralizes **global and system** config only.
  Git still reads the analysis root's own repository-local `.git/config`, which
  can define program-executing settings (`diff.external`, a diff driver's
  `textconv`, `core.fsmonitor`). Environment scrubbing does not cover those, so
  every git argv additionally pins them with runner-owned `-c` overrides
  (`core.pager=cat`, `core.fsmonitor=`) and, on the diff-producing operations,
  the purpose-built `--no-ext-diff`/`--no-textconv` flags. These `-c` values are
  fixed literals owned by the runner and never derived from a parameter — issue
  #27 named *caller-supplied* `-c` as an injection vector, and that stays
  impossible here because a caller can never reach this list;
- `GIT_PAGER`/`PAGER=cat` and `GIT_TERMINAL_PROMPT=0`;
- `GIT_OPTIONAL_LOCKS=0` and `GIT_ALLOW_PROTOCOL=""`.

The report lists the exact environment keys the child received so a reader can
confirm the scrub.

## Output and report

The runner prints one JSON report to stdout. Child output is captured into
`observations.stdout_excerpt` / `stderr_excerpt`, each bounded by the byte cap
with a visible `*_truncated` flag — truncation is never silent. The report also
records the resolved `argv`, the scrubbed environment keys, the validated
parameters, timings, and a `limitations` list.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Operation completed successfully. |
| `2` | Refused on policy or input: unknown operation ID, bad root, missing/unknown/malformed parameter, path escape, or a value that fails its kind. Nothing ran. |
| `3` | Unavailable: the operation's tool is not installed. Report the modality as unreached — do not delegate to an unconstrained agent. |
| `124` | Timeout reached; the runner terminated the process group. |
| `125` | Stdout or stderr exceeded its cap; the runner terminated the process group. |
| `126` | The tool could not be spawned. |
| other | Tool nonzero exit code, propagated unchanged. For a search operation this is scoped negative evidence — `git grep` exits `1` when the pattern matches nothing — not a signal that the modality was unreachable. |

Exit `3` is the acceptance-critical path: a caller that asked for enforced
evidence gets either the evidence (`0`) or an explicit, machine-readable
"unavailable", never a silent downgrade. Only exit `3` (or a spawn/timeout
failure) licenses reporting a modality as unreached. A propagated nonzero from a
search operation is a *negative result under enforcement* — the search ran and
found nothing — and must not be read as grounds to fall back to unconstrained
delegation.

## Security boundary — what is and is not enforced

Enforced by this runner:

- Only a shipped, plugin-owned operation can run; there is no config to edit.
- Each argv is built from a fixed template; parameters are validated and
  positionally placed, never interpolated into flags.
- No shell is ever invoked; there is no metacharacter, glob, or substitution
  surface.
- Path parameters are confined inside the resolved analysis root.
- The environment is rebuilt to strip redirection and pager-exec vectors.

Not established by this runner:

- That the installed `git`/`jq`/`yq` binary is itself free of side effects. The
  catalog is read-only by construction, but the runner cannot audit the tool.
- Freedom from every repository-local `.git/config` program-executing setting.
  The runner pins the ones it knows (`diff.external`, `core.pager`,
  `core.fsmonitor`, and textconv on the diff-producing operations), but a repo
  whose local config defines a diff driver or other program-running setting the
  runner does not pin could still reach it. The mitigating fact is that
  `.git/config` is not clone-transferable — reaching this requires prior local
  write access to the repository being analyzed, not merely cloning it.
- Host command policy. Granting the runner in a host does not grant arbitrary
  Bash through it, and broad host Bash does not make direct shell execution part
  of this skill's sanctioned path.
- Coverage of code-intelligence, and of YAML when `yq` is absent. Those remain
  delegation-only or unavailable, and the skill discloses them as such rather
  than faking an enforced operation.
