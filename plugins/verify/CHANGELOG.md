# Changelog

## 0.3.0 - 2026-07-25

- Define the evidence forms `verify` owns: repository `path:line`, an
  observation form (exact command ID plus artifact pointer) for a claim
  reassessed from a supplied report, and `none`. Dependents inherit these
  instead of widening the slot themselves.
- Close the `unable-to-check` dead end. `verify-before-trust`, the verifier, the
  checklist, and the change-impact report contract now name
  `/collect-runtime-evidence` as the escalation for an unresolved runtime claim
  when `runtime-evidence` is installed, and require the same claim to be
  reassessed here rather than gaining a parallel verdict set. The escalation
  stays optional; `verify` does not depend on its own dependent.
- Fix the `change-impact` tool declaration, which prescribed history and
  structured-data inspection it had no grant to perform. Rather than granting
  commands — a prefix-matched allowlist cannot express "read-only", since
  `git diff`/`git show` accept `--output=<file>`, `git grep` accepts
  `--open-files-in-pager=<cmd>`, and `yq -i` rewrites in place — the skill now
  states an explicit tool boundary and routes every non-lexical modality to
  `retrieval-strategist` or `code-search`.
- Make `verify-before-trust` prose host-neutral by describing read-only search
  and reading by capability instead of Claude-specific tool names.

## 0.2.0 - 2026-07-18

- Add the read-only `change-impact` skill and `/analyze-impact` command for
  prospective blast-radius analysis.
- Define a progressive-disclosure report contract that maps direct dependents,
  symbols and call sites, runtime/config/data/schema surfaces, tests,
  docs/operations, compatibility risks, unknowns, and evidence.
- Reuse `retrieval-core` search modalities and the verifier verdict taxonomy,
  while keeping `plan-execute` optional for broad parallel coverage.
- Distinguish observed impact from inferred risk and unknowns, and make scoped
  negative evidence explicitly weaker than proof of absence.

## 0.1.1 — 2026-07-18

- Order the install snippets in the `verify-before-trust` skill GitHub Copilot →
  APM → Claude Code. Claude Code stays fully supported.

## 0.1.0 — 2026-07-18

- Initial release.
- Add the read-only `verifier` subagent for checking claim sets against the
  actual repository with per-claim verdicts and `file:line` evidence.
- Add the `verify-before-trust` skill for main-agent verification discipline.
- Compose with `retrieval-core` so verification can use the retrieval strategy
  spine to locate evidence efficiently.
