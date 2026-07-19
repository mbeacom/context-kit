---
name: change-impact
description: "Use when analyzing a proposed code, config, API, data, or schema change for blast radius, downstream dependencies, compatibility risks, tests, or operations."
license: MIT
metadata:
  author: Mark Beacom
  version: "0.1.0"
allowed-tools: Read Grep Glob Bash
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
  part of this capability.
- Treat a described future change, uncommitted diff, commit, PR, or design note
  as input evidence, not permission to modify the tree.

## Analysis flow

1. **Normalize the proposed change.** Identify the exact symbols, files, public
   contracts, configuration keys, environment variables, data fields, schema
   objects, generated artifacts, or operational behaviors expected to change.
   Record assumptions when the proposal is underspecified.
2. **Choose retrieval modalities.** Apply `retrieval-strategy`. Use lexical
   search for exact names, code intelligence for definitions and references,
   structural search for code shapes, structured-data search for manifests and
   config, and history search when compatibility intent or prior migrations
   matter. Invoke the read-only `retrieval-strategist` when the repository is
   unfamiliar or the right modality is unclear.
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
