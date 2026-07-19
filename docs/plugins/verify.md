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
| **unable-to-check** | No accessible evidence in the corpus. |

Change-impact is also read-only and prospective. It may inspect search,
code-intelligence, structured data, and history, but does not edit files, generate
artifacts, run tests, start services, or apply migrations. It separates observed
repository coupling from inferred future risk and unknowns:

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
