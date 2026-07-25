# Verdicts

Use one verdict per atomic claim. Keep the line short enough to scan, but include
the evidence that made the verdict possible.

Exact output line format:

```text
VERDICT — claim — evidence (<reference>) — note
```

## Evidence forms

This skill owns the taxonomy, so it also owns the evidence slot. Use exactly one
of these three forms; do not invent another.

- **Repository evidence** — `path:line`. The required form for any verdict
  settled by static inspection. Use multiple citations when one line is not
  enough, such as `evidence (src/a.ts:12; src/b.ts:40)`.
- **Observation evidence** — an observation source plus at least one artifact
  pointer. The source is `command-id=<exact allowlist key>` for the sanctioned
  `runtime-evidence` runner, or `tool=<approved tool>@<target>` for an approved
  optional tool (browser, debugger, container, device) used when no reviewed
  command can represent the claim:

  ```text
  evidence (command-id=api-health; report=${CONTEXT_KIT_DATA}/runtime-evidence/run-4213.json)
  evidence (tool=browser@https://staging.example/health; trace=${CONTEXT_KIT_DATA}/runtime-evidence/run-4219-trace.zip)
  ```

  Use it only when the caller supplied an observed result. Keep the exact source
  identity rather than a reconstructed command line, and never rewrite an
  observation as a `path:line`. An observation with no artifact pointer is not
  citable here — it stays `unable-to-check`, naming what would need to be
  captured.
- **No evidence** — `evidence (none)`. Allowed only for `dubious` and
  `unable-to-check`. An `unable-to-check` verdict that follows an inconclusive
  collection should cite the observation form instead, so the failed attempt is
  recorded rather than blindly repeated.

One verdict cites one form. On reassessment the observation citation *replaces*
the evidence slot rather than joining it — keep any static context that still
matters in the note. Do not merge forms, and do not split the claim to
accommodate both; the claim wording stays fixed.

## Confirmed

The repository directly supports the claim.

```text
confirmed — "The verifier is read-only." — evidence (plugins/verify/agents/verifier.md:5) — tools are limited to Read, Grep, and Glob.
confirmed — "The plugin depends on retrieval-core." — evidence (plugins/verify/.claude-plugin/plugin.json:12) — dependencies includes retrieval-core.
```

## Dubious

The claim is partly true, stale, too broad, or missing a caveat. Use this when
the claim's framing would mislead even though some supporting evidence exists.

```text
dubious — "All auth routes use the new middleware." — evidence (src/routes/admin.ts:18; src/routes/public.ts:9) — admin uses it, but public routes still bypass it.
dubious — "The docs are current." — evidence (README.md:32; package.json:6) — install command matches, but the documented version lags the package version.
```

## Refuted

The repository contradicts the claim. Cite the contradicting line.

```text
refuted — "The package is private." — evidence (package.json:4) — private is false.
refuted — "The API route is removed." — evidence (src/app/api/search/route.ts:1) — the route file still exists and exports handlers.
```

## Unable-to-check

Read-only file inspection cannot settle the claim. Say what would settle it.

```text
unable-to-check — "The migration succeeds against production data." — evidence (none) — requires running the migration or inspecting production-like data.
unable-to-check — "The page renders without hydration warnings." — evidence (none) — requires a browser/runtime check or a test that asserts it.
```

Always name the check that would settle it — that sentence is the handoff, not a
disclaimer. When the claim concerns runtime behavior and the `runtime-evidence`
plugin is installed, the named check can be escalated with
`/collect-runtime-evidence`, passing this claim and this `unable-to-check`
result as the reason it is necessary. Escalation is optional and never
automatic: it needs a reviewed allowlist command ID, and verification itself
stays read-only.

## Revisiting a verdict after observation

An `unable-to-check` verdict is provisional. When an observation returns for the
same atomic claim, replace the verdict instead of emitting a second one:

1. Reuse the original atomic claim verbatim so the before/after pair matches.
2. Read the reported observations, limitations, and cleanup status. Treat exit
   `0` as evidence that the process completed, not as automatic confirmation of
   the claim.
3. Assign the new verdict from the same four values and cite the observation
   evidence form.
4. Keep `unable-to-check` when the run timed out, hit an output cap, failed to
   spawn, or observed something the claim does not depend on. Name the
   limitation that blocked it, and still cite the observation form — an
   inconclusive attempt is provenance worth carrying forward.

```text
unable-to-check — "The health endpoint reports degraded when the cache is down." — evidence (none) — requires running the service; no static assertion covers it.
confirmed — "The health endpoint reports degraded when the cache is down." — evidence (command-id=health-cache-down; report=${CONTEXT_KIT_DATA}/runtime-evidence/run-4213.json) — exit 0; response body contained a degraded status.
unable-to-check — "The health endpoint reports degraded when the cache is down." — evidence (command-id=health-cache-down; report=${CONTEXT_KIT_DATA}/runtime-evidence/run-4217.json) — terminated at the 30s timeout before responding; raise the timeout or use a narrower reviewed command.
dubious — "The settings page renders without hydration warnings." — evidence (tool=browser@https://staging.example/settings; console=${CONTEXT_KIT_DATA}/runtime-evidence/run-4219-console.log) — no warnings at the observed viewport; other viewports and routes were not exercised.
```

Never restate an observation as repository evidence, and never imply that a
command's side effects were reversed.

## Edge cases

- True in general but false for this repository: use refuted if repo evidence
  directly contradicts the claim; use dubious if the claim is merely too broad or
  missing a repo-specific caveat.
- Runtime behavior: mark unable-to-check unless static evidence directly proves
  it, such as a passing test fixture, route registration, feature flag config, or
  schema constraint. Name the observation that would settle it so the claim can
  be escalated instead of silently dropped.
- Missing implementation: "not found" is unable-to-check or dubious unless you
  found a definitive registry, manifest, or exhaustive entry point that proves
  absence.
- Conflicting evidence: use dubious when primary files disagree, and cite both
  sides. Use refuted only when the primary source of truth contradicts the claim.
