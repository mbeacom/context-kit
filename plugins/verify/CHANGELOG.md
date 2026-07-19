# Changelog

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
