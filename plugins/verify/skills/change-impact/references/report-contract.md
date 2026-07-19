# Change-impact report contract

Use this contract for every change-impact report. Keep all sections, writing
`None observed` or `Unknown` rather than silently omitting a surface.

## Evidence model

Keep impact basis separate from verification verdict.

### Impact basis

- **observed** - Repository evidence directly establishes a dependency,
  consumer, contract, or operational surface connected to the proposed change.
  Cite `path:line`.
- **inferred** - Evidence establishes a plausible propagation path, but the
  breakage or required response depends on an assumption about the unimplemented
  change or runtime behavior. Cite the observed basis and state the assumption.
- **unknown** - Read-only repository inspection cannot settle whether or how the
  surface is affected. State the evidence, access, runtime observation, or
  decision needed to resolve it.

Observed means "the coupling exists," not "the future change will definitely
break it." A call site can be observed while its compatibility risk remains
inferred.

### Verification verdict

Apply the existing verify taxonomy to each atomic factual claim:

- **confirmed** - Primary evidence directly supports the claim.
- **dubious** - Evidence is partial, conflicting, stale, too broad, or missing a
  material caveat.
- **refuted** - Primary evidence directly contradicts the claim.
- **unable-to-check** - Read-only inspection cannot settle the claim.

Use the detailed rules in
`../../verify-before-trust/references/verdicts.md`. Reserve `refuted` for
contradiction, not an unsuccessful search.

### Risk priority

- **high** - Likely contract break, data loss/corruption, security boundary
  change, outage path, or rollback blocker.
- **medium** - Likely behavior change, coordinated consumer update, test gap, or
  operational adjustment without evidence of catastrophic failure.
- **low** - Localized update, documentation drift, or defensive follow-up with a
  narrow propagation path.
- **unknown** - Consequence cannot be prioritized from available evidence.

Risk priority is prospective judgment. Label it as inferred unless repository
evidence directly documents the consequence.

## Required report

Render sections in this order.

### 1. Proposed change

State:

- the normalized change;
- change anchors (symbols, files, keys, endpoints, events, tables, fields, or
  formats);
- input basis (description, diff, commit, PR, or design document);
- assumptions and exclusions.

### 2. Executive blast radius

Provide:

- direct dependents observed;
- highest-priority inferred risks;
- affected surface count by category;
- overall confidence (`high`, `medium`, or `low`) with a one-sentence reason;
- top unknowns that could materially expand or shrink the radius.

Do not replace the detailed map with this summary.

### 3. Direct dependency map

List every observed direct edge from a change anchor. Include incoming and
outgoing edges when both affect compatibility.

```text
ANCHOR -> DEPENDENT | relationship | VERDICT | evidence (path:line)
```

Examples of relationships: imports, calls, implements, registers, serializes,
parses, reads-config, writes-field, consumes-event, generates, packages, or
deploys.

Keep transitive candidates out of this section unless an explicit path is
observed. Put those candidates in the surface table as inferred.

### 4. Impact surface table

Use exactly these columns:

| ID | Surface | Candidate impact | Basis | Verdict | Priority | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- | --- | --- |

Include rows for all of these surface groups:

1. symbols and call sites;
2. runtime and integration wiring;
3. configuration and environment;
4. data, schema, migration, serialization, and generated artifacts;
5. tests and fixtures;
6. docs, deployment, rollback, observability, runbooks, and support;
7. compatibility (source, binary, behavioral, data, protocol, and rollout).

For `observed`, include at least one `path:line` citation. For `inferred`, cite
the observed basis and spell out the assumption. For `unknown`, use
`evidence (none)` only when no repository evidence exists and make the follow-up
specific.

### 5. Compatibility assessment

Address each category explicitly:

- source/API compatibility;
- binary/package compatibility when relevant;
- behavioral/runtime compatibility;
- data/schema/wire-format compatibility;
- configuration and deployment compatibility;
- mixed-version rollout and rollback compatibility.

State `not applicable` with a reason when a category truly does not apply.

### 6. Test and evidence gaps

Separate:

- tests that directly cover a change anchor;
- tests that cover an affected dependent;
- missing contract, migration, integration, rollback, or mixed-version coverage;
- executable checks that would settle unknowns.

Name commands only as recommended follow-ups. Do not run them during a
read-only impact analysis.

### 7. Unknowns and search limits

For every material unknown, state:

- why repository inspection cannot settle it;
- what could change the conclusion;
- the minimum evidence needed next.

Also summarize corpus boundaries, excluded/generated/vendor paths, unavailable
tools or services, and search modalities used.

### 8. Conclusion

State the smallest defensible blast-radius conclusion. Use:

```text
Observed impact: <directly evidenced scope>.
Inferred risk: <prospective propagation and assumptions>.
Not established: <material unknowns and unsearched/external scope>.
```

## Absence and negative evidence

Never convert an empty result into proof of absence unless an exhaustive source
of truth was inspected, such as a complete registry, manifest, schema, or
closed-world entry-point list.

Acceptable:

```text
No additional consumers were observed for `user.deleted` in `src/` and `tests/`
using lexical references plus the event registry. External consumers remain
unknown.
```

Not acceptable:

```text
There are no other consumers.
```

When a complete registry supports absence, cite it and keep the claim atomic so
the verifier taxonomy can assess it.

## Compact example row

```text
| CI-03 | data/schema | Older consumers may reject `user_id` | inferred | confirmed | high | events/schema.json:41; src/consumer.ts:88 | Inspect deployed consumer versions and add a mixed-version contract test |
```

The verdict confirms the cited facts (the schema field and parser behavior); it
does not convert the prospective rejection into an observed runtime failure.
