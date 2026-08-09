---
name: change-impact
description: "Use when analyzing a proposed code, config, API, data, or schema change for blast radius, downstream dependencies, compatibility, tests, or operations."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob
---

# Change Impact

Analyze a proposed change without implementing or executing it. Trace repository
evidence outward from the change anchors, distinguish observed coupling from
inferred risk, and report what remains unknown.

Use this skill for prospective questions such as:

- "What is the blast radius of changing this interface?"
- "Which callers, tests, configs, and runbooks would this migration affect?"
- "Analyze the impact of removing this feature flag."
- "What could break if this event payload changes?"

Use `verify-before-trust` instead when the task is only to judge whether an
existing claim is true. Use an implementation or planning workflow instead when
the request is to edit files, run migrations, execute tests, or produce an
implementation plan.

## Read-only boundary

Keep the analysis prospective and non-mutating.

- Read files and use search, code-intelligence, structured-data, and history
  inspection only.
- Do not edit files, generate artifacts, install dependencies, run tests, start
  services, apply migrations, or invoke commands that can change repository or
  environment state.
- State executable checks as follow-up evidence needed; do not perform them as
  part of this capability. When an unknown hinges on runtime behavior and the
  `runtime-evidence` plugin is installed, name `/collect-runtime-evidence` and
  the claim it would settle, and leave the collection to that separate,
  explicitly invoked workflow.
- Treat a described future change, uncommitted diff, commit, PR, or design note
  as input evidence, not permission to modify the tree.

### Tool boundary

A skill's `allowed-tools` pre-approves a surface; it does not deny the rest, and
it is not a portable control across hosts. So the declaration below is intent,
not enforcement — but this skill also ships an enforced path for the modalities
where intent was not enough. The catalog's boundary map in `docs/security.md`
holds the precise version; keep this section honest with it.

- **Declared here.** File reading plus name and content search, with no command
  grant. A prefix-matched command allowlist could not express "read-only"
  anyway: `git diff`/`git show` accept an `--output` write flag, `git grep`
  accepts an `--open-files-in-pager` exec flag, and `yq` rewrites in place with
  its in-place flag.
- **Enforced by the inspection runner.** `scripts/run-impact-inspection.py` is a
  stdlib, no-shell executor with a fixed, plugin-owned catalog of read-only
  operations. It reaches history (git log/show/diff/blame), structural
  (`git grep`), structured-data (`jq`, and `yq` when installed), and governance
  (`adr explain`/`adr check`, when adrkit is installed) under a
  genuinely non-mutating constraint: it builds each argv itself, validates and
  positionally substitutes parameters, confines paths to the analysis root,
  scrubs the environment, and never invokes a shell. See
  [references/inspection-runner.md](references/inspection-runner.md). Prefer it
  whenever a caller needs an actual guarantee for these modalities.
- **Reached by delegation.** `retrieval-strategist` declares unrestricted
  `Bash`; `code-search` declares `Bash(git:*)` and `Bash(yq:*)`. Their
  non-mutating character is an instruction they follow, not a restriction their
  grants impose. Use delegation for code-intelligence, and only fall back to it
  for the runner's modalities when the runner reports the tool unavailable and
  the caller accepts an unenforced surface.

| Modality | Enforced path | Delegation-only fallback |
| --- | --- | --- |
| lexical, file reading | this skill's Read/Grep/Glob | — |
| history | runner: `git-log-*`, `git-show-commit`, `git-diff-revs`, `git-blame-path` | `retrieval-strategist`, or `code-search` when installed |
| structural | runner: `git-grep` | `retrieval-strategist`, or `code-search` when installed |
| structured-data | runner: `json-*`; `yaml-*` when `yq` is installed | `retrieval-strategist`, or `code-search` when installed |
| governance | runner: `adr-explain-path`, `adr-check-path`, when adrkit is installed | — (no fallback; report unreached) |
| code-intelligence | — (no enforced operation) | `retrieval-strategist`, or `code-search` when installed |
| factual claim checks | `verifier` (Read/Grep/Glob grant) | — |
| runtime observation | `/collect-runtime-evidence` only, never here | — |

The runner never silently downgrades. When the requested tool is missing, the
operation ID is unknown, or a parameter fails validation, it exits non-zero with
a machine-readable refusal or `unavailable` status. On `unavailable`, report the
modality as unreached in section 7 of the report contract rather than quietly
delegating; delegate only as a disclosed, unenforced choice, and never treat
delegation as a way around this skill's own declaration.

Where no enforced operation exists — code-intelligence, and YAML when `yq` is
absent — do not fake one. Disclose the modality as reached only by delegation,
or as unreached, and say which.

## Analysis flow

1. **Normalize the proposed change.** Identify the exact symbols, files, public
   contracts, configuration keys, environment variables, data fields, schema
   objects, generated artifacts, or operational behaviors expected to change.
   Record assumptions when the proposal is underspecified.
2. **Choose retrieval modalities.** Apply `retrieval-strategy`. Use lexical
   search for exact names, code intelligence for definitions and references,
   structural search for code shapes, structured-data search for manifests and
   config, and history search when compatibility intent or prior migrations
   matter. When the repository keeps an ADR corpus, also run a **governance**
   check (`adr-explain-path`) on the paths the change touches: it reports the
   decisions that bind them, including rejected and superseded ones, so a
   settled question is not re-opened by accident. Treat a missing corpus or a
   missing `adr` binary as an unreached modality, never as "nothing governs
   this" — and report a governing record as a *finding* only when it changes the
   conclusion; when the same constraint already sits in always-on instructions or
   a CI gate, cite it as provenance, not as a discovery. Run lexical search and
   file reading here. For history,
   structured-data, and `git grep` structural search, prefer the enforced
   inspection runner (`scripts/run-impact-inspection.py`, see the tool boundary
   above); reach code-intelligence — and any modality the runner reports
   unavailable — by delegation, disclosing it as unenforced. Invoke
   `retrieval-strategist` when the repository is unfamiliar or the right modality
   is unclear, constraining it to inspection.
3. **Trace direct dependents first.** Find imports, references, callers,
   implementers, registries, serializers, consumers, build/package edges, and
   generated-code sources that directly depend on each change anchor. Do not
   jump from a broad text match to a dependency claim.
4. **Expand across required surfaces.** Inspect:
   - symbol definitions, call sites, implementations, and public API consumers;
   - runtime wiring, routes, jobs, events, feature flags, config, and secrets;
   - data models, storage formats, schemas, migrations, fixtures, and generated
     representations;
   - unit, integration, contract, end-to-end, migration, and snapshot tests;
   - user docs, API docs, runbooks, dashboards, alerts, deployment, rollback,
     and support procedures;
   - source, binary, behavioral, data, protocol, and rollout compatibility.
5. **Verify factual findings.** Apply the existing verifier taxonomy to atomic
   claims: confirmed, dubious, refuted, or unable-to-check. Delegate a large
   claim set to the read-only `verifier` when an independent evidence pass would
   reduce author-grading-own-work bias.
6. **Classify the impact basis.** Label each item as observed, inferred, or
   unknown according to `references/report-contract.md`. Never present an
   inferred outcome as observed repository behavior.
7. **Stop at useful coverage.** Report the searched scope and residual risk.
   Do not claim complete coverage solely because searches returned no matches.
8. **Render the exact contract.** Follow
   `references/report-contract.md`, including all required sections and evidence
   fields.

## Coverage discipline

For every change anchor, seek both dependency directions where they matter:

- **Incoming:** callers, consumers, implementers, readers, parsers, deployment
  inputs, and operational users.
- **Outgoing:** dependencies invoked by the changed code, schemas emitted,
  side-effects produced, and contracts assumed.

Report direct dependents separately from transitive candidates. Treat transitive
impact as inferred until a concrete path from the proposed change to the
dependent is established.

Record searches that found no relevant results as scoped negative evidence:
name the modality, query concept, and corpus boundary. Phrase the conclusion as
"no impact observed in the searched scope," not "no impact exists."

## Broad repositories

Use `retrieval-strategist` to partition retrieval by modality or subsystem. If
`plan-execute` is installed, optionally use its plan-big/execute-small
orchestration for broad parallel read-only coverage. Constrain every worker to
inspection and evidence gathering; do not make `plan-execute` a dependency and
do not permit implementation work.

## Usage examples

Positive:

```text
Analyze the blast radius of changing Account.id from an integer to a UUID.
Map the downstream impact of removing PAYMENT_RETRY_LIMIT.
/analyze-impact Rename the user.deleted event field from id to user_id.
```

Negative:

```text
Update Account.id to UUID and fix every caller.        # implementation request
Run the migration and tell me whether production data survives. # executable check
Verify that the README's install command is correct.   # verify-before-trust
Write a full implementation plan for the event rename. # planning workflow
```

For mixed requests, produce the read-only impact report only when explicitly
separable; otherwise route to the requested implementation, execution, or
planning workflow.

## Additional resource

Read **`references/report-contract.md`** before reporting. It defines the
required sections, impact/evidence labels, compatibility categories, absence
language, and exact row format.
