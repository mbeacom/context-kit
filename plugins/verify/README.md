# verify

Read-only claim verification and prospective change-impact analysis for
codebases. `verify` gives agents a disciplined way to check AI answers, plans,
PR descriptions, migration notes, and docs against the actual repository, and
to map the blast radius of a proposed change before implementation.

## Install

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install verify@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install verify@context-kit
```

The APM install also deploys `retrieval-core`, the retrieval spine this plugin
uses to find evidence efficiently.

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install verify@context-kit
```

## Components

| Component | What it is |
| --- | --- |
| **`verifier`** subagent | A read-only verifier with only `Read`, `Grep`, and `Glob`. It checks a claim set against the repository and returns per-claim verdicts with `file:line` evidence. |
| **`verify-before-trust`** skill | A main-agent discipline for decomposing claims, locating primary evidence, assigning verdicts, and deciding when to delegate verification to the `verifier` subagent. |
| **`change-impact`** skill | A read-only, prospective blast-radius analysis that maps direct dependents, call sites, runtime/config/data/schema surfaces, tests, docs/operations, compatibility risks, and unknowns. |
| **`/analyze-impact`** command | Runs the `change-impact` contract for a proposed change, diff, commit, PR, or design decision without editing files or executing tests or migrations. |

## Read-only by design

The verifier cannot edit files, write files, or run shell commands. That makes it
safe to use as an independent second read: it can confirm, question, or refute
claims without mutating the tree or grading its own changes.

Change-impact analysis is also non-mutating. It may use read-only search,
code-intelligence, structured-data, and history inspection, but it does not run
tests, start services, generate artifacts, or apply migrations. Its report
separates observed repository coupling from inferred future risk and from
unknowns that need runtime or external evidence.

## Retrieval-core composition

`verify` depends on `retrieval-core`. Use the `retrieval-strategy` decision flow
when it is not obvious how to find evidence: scope the corpus first, search
cheaply, read primary files directly, then cite exact `path:line` support.

The `change-impact` skill uses the same spine to compose lexical, structural,
code-intelligence, structured-data, and history search. For broad repositories,
the optional `plan-execute` plugin can parallelize read-only coverage; it is not
a dependency.

## Change-impact report

Run:

```text
/analyze-impact Change Account.id from an integer to a UUID
```

The report includes the normalized proposal, executive blast radius, direct
dependency map, required impact surfaces, compatibility assessment, test and
evidence gaps, unknowns/search limits, and a conclusion that distinguishes:

- **Observed impact** - dependencies and contracts directly evidenced in the
  repository.
- **Inferred risk** - prospective outcomes based on observed coupling and stated
  assumptions.
- **Not established** - external, runtime, or unsearched scope that repository
  inspection cannot prove.

An empty search result is reported only as "no impact observed in the searched
scope" unless a cited closed-world registry or manifest proves absence.
