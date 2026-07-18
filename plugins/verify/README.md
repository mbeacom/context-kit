# verify

Read-only claim verification for codebases. `verify` gives agents a disciplined
way to check AI answers, plans, PR descriptions, migration notes, and docs
against the actual repository before relying on them.

## Install

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install verify@context-kit
```

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

## Components

| Component | What it is |
| --- | --- |
| **`verifier`** subagent | A read-only verifier with only `Read`, `Grep`, and `Glob`. It checks a claim set against the repository and returns per-claim verdicts with `file:line` evidence. |
| **`verify-before-trust`** skill | A main-agent discipline for decomposing claims, locating primary evidence, assigning verdicts, and deciding when to delegate verification to the `verifier` subagent. |

## Read-only by design

The verifier cannot edit files, write files, or run shell commands. That makes it
safe to use as an independent second read: it can confirm, question, or refute
claims without mutating the tree or grading its own changes.

## Retrieval-core composition

`verify` depends on `retrieval-core`. Use the `retrieval-strategy` decision flow
when it is not obvious how to find evidence: scope the corpus first, search
cheaply, read primary files directly, then cite exact `path:line` support.
