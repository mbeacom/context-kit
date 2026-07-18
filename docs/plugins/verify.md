# verify

!!! abstract "Read-only claim verification"
    A disciplined way to check AI answers, plans, PR descriptions, migration
    notes, and docs against the actual repository before relying on them — with
    per-claim verdicts backed by `file:line` evidence.

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

## Composing with retrieval-core

When it isn't obvious how to find evidence, use the `retrieval-strategy` decision
flow: scope the corpus first, search cheaply, read primary files directly, then
cite exact `path:line` support.

## At a glance

| | |
| --- | --- |
| **Category** | verification |
| **Provides** | `verifier` subagent (Read/Grep/Glob only) + a skill |
| **Dependencies** | [`retrieval-core`](retrieval-core.md) |
| **License** | MIT |
