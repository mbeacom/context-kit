# Verdicts

Use one verdict per atomic claim. Keep the line short enough to scan, but include
the evidence that made the verdict possible.

Exact output line format:

```text
VERDICT — claim — evidence (path:line) — note
```

Use multiple citations in the evidence slot when a verdict needs more than one
line, such as `evidence (src/a.ts:12; src/b.ts:40)`.

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

## Edge cases

- True in general but false for this repository: use refuted if repo evidence
  directly contradicts the claim; use dubious if the claim is merely too broad or
  missing a repo-specific caveat.
- Runtime behavior: mark unable-to-check unless static evidence directly proves
  it, such as a passing test fixture, route registration, feature flag config, or
  schema constraint.
- Missing implementation: "not found" is unable-to-check or dubious unless you
  found a definitive registry, manifest, or exhaustive entry point that proves
  absence.
- Conflicting evidence: use dubious when primary files disagree, and cite both
  sides. Use refuted only when the primary source of truth contradicts the claim.
