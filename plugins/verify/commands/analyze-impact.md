---
description: Analyze the prospective blast radius of a proposed code, config, API, data, or schema change without modifying or executing the repository.
argument-hint: <proposed change, diff, commit, PR, or design decision>
---

Analyze `$ARGUMENTS` with the `change-impact` skill.

If `$ARGUMENTS` is empty, ask for the proposed change or the diff, commit, PR, or
design document that defines it. Do not infer an arbitrary target.

Read and follow
`${CLAUDE_PLUGIN_ROOT}/skills/change-impact/references/report-contract.md`
(resolve it from this plugin's install directory). Keep the operation read-only
and prospective:

- do not edit files, generate artifacts, install dependencies, run tests, start
  services, or apply migrations;
- use `retrieval-strategy` and, when useful, the read-only
  `retrieval-strategist` to locate definitions, references, call sites, config,
  schemas, tests, docs, and operational evidence;
- use the existing `verifier` and its confirmed/dubious/refuted/unable-to-check
  taxonomy for factual claims that benefit from an independent pass;
- if `plan-execute` is installed and the repository is broad, optionally
  parallelize read-only evidence collection, but do not require it or permit
  workers to implement changes.

Return the complete blast-radius report contract. Explicitly distinguish
observed impact from inferred risk and unknowns. Treat no matches as scoped
negative evidence, not proof that no impact exists.
