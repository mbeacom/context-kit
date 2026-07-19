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
