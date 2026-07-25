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
4. Search read-only with file-name and content search, then read the primary
   files directly. Keep the search scope narrow before opening whole files.
5. Assign one verdict per claim using the taxonomy in
   `references/verdicts.md`: confirmed, dubious, refuted, or unable-to-check.
6. Summarize the counts and hand off any follow-up that needs executable
   verification, naming the specific command or observation rather than saying
   more testing is needed.

## Evidence standard

- Cite `file:line` evidence for every confirmed or refuted verdict settled by
  static inspection. `references/verdicts.md` defines the only other accepted
  form, for verdicts reassessed from a supplied observation report.
- Prefer primary evidence over secondary evidence. Code/config/tests beat
  comments/docs; comments/docs beat issue summaries or AI explanations.
- Do not treat "I did not find it" as proof of falsehood. Use refuted only when
  found evidence contradicts the claim.
- If a claim is about runtime behavior, use static evidence only when it directly
  proves the behavior, such as a test, route registration, or config branch.
  Otherwise mark it unable-to-check and name the command or observation that
  would settle it.

## Escalating an unresolved runtime claim

`unable-to-check` is a routing decision, not an ending. Keep the claim atomic and
carry the static result forward as the reason execution is warranted.

When the `runtime-evidence` plugin is installed, escalate with
`/collect-runtime-evidence`, which runs a pre-reviewed allowlist command ID, or
an approved browser/debugger observation when no reviewed command can represent
the claim.
Return its report here and reassess the same claim under this taxonomy — the
verdict stays owned by verification. Do not invent a runtime-specific verdict set
and do not run the command as part of verification itself.

When it is not installed, leave the verdict at `unable-to-check` and state the
missing capability. When it is installed but no reviewed command ID matches, the
claim can still route to that plugin's approved optional-tool path — a browser,
debugger, or container observation, which exists precisely for claims no reviewed
command can represent, and which returns the `tool=…@…` evidence source. Leave
the verdict at `unable-to-check` only when neither a reviewed command ID nor an
approved, available tool can collect the observation. That is a valid outcome;
guessing is not.

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

GitHub Copilot CLI installs this plugin directly:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install verify@context-kit
```

APM installs the same plugin, and its manifest also pulls `retrieval-core`:

```bash
apm marketplace add mbeacom/context-kit
apm install verify@context-kit
```

Claude Code installs it via `/plugin`:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install verify@context-kit
```
