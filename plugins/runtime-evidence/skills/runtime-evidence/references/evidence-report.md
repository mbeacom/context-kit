# Evidence Report

Use the runner JSON as the primary handoff artifact. Summarize it without
discarding failures or limitations.

## Required handoff

```text
Claim: <atomic claim>
Reproduction command ID: <exact config key>
Environment: <label>; cwd=<path>; platform=<platform>; python=<version>
Observations:
- exit_code=<code>; termination_reason=<reason>
- stdout=<artifact pointer>; bytes=<captured>; truncated=<true|false>
- stderr=<artifact pointer>; bytes=<captured>; truncated=<true|false>
Artifact/output pointers:
- report=<path>
- config=<path>; sha256=<digest>
Verdict-ready evidence:
- <fact directly observed>
Limitations:
- <what the run cannot establish>
Cleanup status: <not-needed|process-group-killed|...>
```

Keep the exact command ID rather than reconstructing a command line. The config
and digest are the reproduction source of truth and avoid leaking arguments into
summaries.

For an approved optional-tool observation, where no reviewed command can
represent the claim, substitute a stable tool identity for the command ID —
`Observation source: tool=<approved tool>@<target>` — and use that path's field
set from the skill's output contract: observed state instead of process exit
data, at least one durable artifact the tool retained, and `not-applicable` for
the config digest. Without a durable pointer the observation is not citable
under `verify`'s evidence forms, so the claim stays `unable-to-check` naming the
artifact that would need capturing. `references/optional-tools.md` governs when
that path is allowed, and it runs in the main agent rather than the
`runtime-investigator` subagent.

## Interpretation

- Treat exit `0` as evidence that the configured process completed, not automatic
  confirmation of the claim. Interpret the observed output and the test's own
  assertions.
- Treat a child nonzero exit as a runtime observation. Preserve it unchanged.
- Treat timeout or output-limit termination as incomplete evidence unless the
  claim specifically concerns that behavior.
- Treat a spawn error as an environment or configuration failure, not application
  behavior.
- Treat truncated output as bounded evidence. Cite the artifact and state that
  later bytes were not retained.
- Treat cleanup status as process-control metadata only. Process-group
  termination does not undo filesystem, database, network, or external-service
  effects.

Pass the resulting facts to `verify` and use its existing `confirmed`, `dubious`,
`refuted`, or `unable-to-check` taxonomy. Do not create a runtime-specific
verdict set.

Cite the observation evidence form that `verify` defines in
`verify-before-trust/references/verdicts.md`: the observation source plus an
artifact pointer, for example `evidence (command-id=<id>; report=<path>)` for an
allowlisted run, or `evidence (tool=<approved tool>@<target>; <artifact>=<path>)`
for an approved optional-tool observation per `references/optional-tools.md`.
Reuse the original claim wording so the reassessed verdict replaces the earlier
`unable-to-check` instead of adding a second entry. Never convert an observation
into a repository `path:line`.
