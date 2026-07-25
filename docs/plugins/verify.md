# verify

!!! abstract "Read-only verification and prospective impact analysis"
    A disciplined way to check AI answers, plans, PR descriptions, migration
    notes, and docs against the actual repository before relying on them — with
    per-claim verdicts backed by `file:line` evidence — and to map the blast
    radius of a proposed change before implementation.

`verify` declares `dependencies: ["retrieval-core"]`, so it composes with the
[retrieval spine](retrieval-core.md) to find evidence efficiently.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install verify@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install verify@context-kit   # also deploys retrieval-core
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install verify@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`verifier`** subagent | A read-only verifier with only `Read`, `Grep`, and `Glob`. Checks a claim set against the repository and returns per-claim verdicts with `file:line` evidence. |
| **`verify-before-trust`** skill | A main-agent discipline for decomposing claims, locating primary evidence, assigning verdicts, and deciding when to delegate to the `verifier`. |
| **`change-impact`** skill | Prospective blast-radius analysis across direct dependents, runtime/config/data/schema surfaces, tests, docs/operations, compatibility, and unknowns. |
| **`/analyze-impact`** command | Applies the change-impact report contract to a proposal, diff, commit, PR, or design decision. |

## Read-only by design

!!! success "Safe as an independent second read"
    The verifier cannot edit files, write files, or run shell commands. It can
    confirm, question, or refute claims without mutating the tree or grading its
    own changes.

Each claim gets one of four verdicts, with evidence:

| Verdict | Meaning |
| --- | --- |
| **confirmed** | Primary evidence supports the claim (`path:line` cited). |
| **dubious** | Evidence is partial, ambiguous, or indirect. |
| **refuted** | Primary evidence contradicts the claim. |
| **unable-to-check** | Read-only inspection cannot settle it. States what would. |

`verify` owns the evidence slot as well as the taxonomy, and defines exactly
three forms so dependents inherit them rather than inventing their own:

| Form | When | Example |
| --- | --- | --- |
| **Repository** | any verdict settled by static inspection | `evidence (src/a.ts:12)` |
| **Observation** | a claim reassessed from a caller-supplied [`runtime-evidence`](runtime-evidence.md) report, including an inconclusive one | `evidence (command-id=api-health; report=…/run-4213.json)` |
| **None** | `dubious` or `unable-to-check` with no report to cite | `evidence (none)` |

One verdict cites one form. On reassessment the observation citation replaces
the evidence slot rather than joining it, and any static context moves to the
note.

### Escalating an unresolved runtime claim

!!! info "`unable-to-check` is a route, not a dead end"
    A runtime claim that static evidence cannot settle must name the observation
    that would settle it. When [`runtime-evidence`](runtime-evidence.md) is
    installed, that observation can be escalated with
    `/collect-runtime-evidence`, which runs only a pre-reviewed allowlist command
    ID. The report comes back here, and the same claim is reassessed under this
    taxonomy — verification keeps ownership of the verdict.

    The escalation is optional. `verify` does not depend on `runtime-evidence`;
    the dependency runs the other way. Without it, `unable-to-check` plus the
    named missing capability is the correct final answer.

Change-impact is prospective and intended to be non-mutating — an intent, not a
guarantee. It declares a surface of file reading plus search with no command
grant, since a prefix-matched allowlist cannot express "read-only" anyway
(`git diff --output=`, `git grep --open-files-in-pager=`, `yq -i`). It reaches
code-intelligence, structured-data, and history only by delegating, and those
delegates declare broader grants.

!!! warning "`allowed-tools` is not an enforcement control"
    Omitting command grants avoids pre-approving them; it does not deny them,
    and it is not portable across hosts. As the [boundary map](../security.md)
    states, host permissions and operator review govern actual execution. A real
    non-mutation guarantee has to come from host permissions, a restricted
    subagent such as `verifier`, or a hook.

It separates observed repository coupling from inferred future risk and
unknowns:

```text
/analyze-impact Change Account.id from an integer to a UUID
```

For broad repositories, `plan-execute` can optionally parallelize read-only
coverage. It is not a dependency and does not permit implementation work.

## Composing with retrieval-core

When it isn't obvious how to find evidence, use the `retrieval-strategy` decision
flow: scope the corpus first, search cheaply, read primary files directly, then
cite exact `path:line` support.

## At a glance

| | |
| --- | --- |
| **Category** | verification |
| **Provides** | `verifier` subagent + 2 skills + `/analyze-impact` |
| **Dependencies** | [`retrieval-core`](retrieval-core.md) |
| **License** | MIT |
