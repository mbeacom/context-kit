---
name: verify-before-trust
description: "Use when you need to check whether claims are actually true before relying on them — verifying an AI answer, a plan's assumptions, a PR description, or docs against the real codebase, and reporting per-claim verdicts with evidence."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob
---

# Verify Before Trust

AI answers, handoff notes, plans, PR descriptions, and docs often mix true
observations with stale context, inferred behavior, or missing caveats. Treat
claims as hypotheses until they are checked against the actual repository.

Use this skill when you want to verify claims yourself in the main context. Use
the `verifier` subagent instead when the claim set is large, when verification
would clutter the main context, or when you want to avoid the
author-grading-own-work bias.

## Verification flow

1. Gather the claim source and quote or paraphrase only the claims that matter.
2. Decompose bundled statements into atomic, checkable claims.
3. For each claim, decide the cheapest likely evidence source: code, config,
   tests, schema, migration, generated manifest, docs, or history surfaced by a
   retrieval pass.
4. Search read-only with `Glob` and `Grep`, then use `Read` to inspect the
   primary files directly.
5. Assign one verdict per claim using the taxonomy in
   `references/verdicts.md`: confirmed, dubious, refuted, or unable-to-check.
6. Summarize the counts and call out any follow-up that needs executable
   verification.

## Evidence standard

- Cite `file:line` evidence for every confirmed or refuted verdict.
- Prefer primary evidence over secondary evidence. Code/config/tests beat
  comments/docs; comments/docs beat issue summaries or AI explanations.
- Do not treat "I did not find it" as proof of falsehood. Use refuted only when
  found evidence contradicts the claim.
- If a claim is about runtime behavior, use static evidence only when it directly
  proves the behavior, such as a test, route registration, or config branch.
  Otherwise mark it unable-to-check and name the command or observation that
  would settle it.

## When to delegate

Delegate to the `verifier` subagent when:

- There are many claims to check and you want a compact result.
- The main agent authored the claims and should not grade its own work.
- You need a read-only second read that cannot edit files or run commands.
- The verification scope crosses enough files that it would pollute the main
  task context.

Keep verification read-only even in the main context unless the caller separately
asks you to run tests or make changes.

## Portability

Claude Code and GitHub Copilot CLI install this plugin directly:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install verify@context-kit
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install verify@context-kit
```

APM users can install the same plugin; the APM manifest also pulls
`retrieval-core`:

```bash
apm marketplace add mbeacom/context-kit
apm install verify@context-kit
```
