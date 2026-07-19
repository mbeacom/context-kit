# Catalog quality reference

Discovery metadata is always-on context: every installed `SKILL.md` and
`agents/*.md` contributes its `name` and `description` before a model chooses
what to load. The catalog gate keeps that shared surface bounded, distinct, and
reviewable with deterministic checks only.

Run:

```bash
bash plugins/plugin-forge/scripts/check-catalog-quality.sh
bash plugins/plugin-forge/scripts/test-catalog-quality.sh
```

The first command reads
`plugins/plugin-forge/quality/discovery-policy.json` and
`plugins/plugin-forge/quality/discovery-fixtures.json`, plus the retrieval
contract corpus in
`plugins/plugin-forge/quality/retrieval-scenarios.json`. The second runs
hermetic Python unit tests and a mocked Node smoke test for the existing
plan-big/execute-small workflow. Neither command uses the network or requires a
model credential.

## Aggregate always-on budget

`aggregate_description_max_chars` caps the sum of the parsed, unquoted
`description` values across every current skill and agent. Character count is
deliberately simple and stable across tokenizers. The validator always reports
current use and the configured limit.

Treat the budget as a catalog-level constraint, not a target. Prefer shorter,
specific triggers and progressive-disclosure references over increasing the
limit. A limit change is an explicit policy review.

## Description similarity

The validator compares every description pair with a deterministic heuristic:

1. Lowercase and extract `[a-z0-9]+` tokens.
2. Remove the fixed boilerplate stopword set in `catalog_quality.py`.
3. Compute Jaccard overlap for unique content tokens.
4. Compute Jaccard overlap for adjacent content-token bigrams.
5. Score `70% × token overlap + 30% × bigram overlap`; when neither
   description has a bigram, use token overlap alone.

A pair fails when its score is greater than or equal to
`similarity_threshold`. This catches near-copy triggers that make routing
boundaries dangerously ambiguous; it is not a semantic-equivalence claim.

When two descriptions must intentionally overlap, add their exact repo-relative
paths to `similarity_allowlist` with a substantive `reason`. Keep the threshold
in policy rather than hiding a different cutoff in code. The validator rejects
unknown, duplicate, self-paired, or unexplained allowlist entries.

## Central discovery fixtures

`discovery-fixtures.json` has one exact path entry for every skill and agent.
Each entry carries at least the policy's minimum positive and negative natural
language queries. Static quality checks require:

- exact component coverage, with no stale or unknown paths;
- non-trivial, globally unique examples;
- a content-term connection between every positive and its description; and
- at least one near-miss negative that shares a description term.

Negatives should exercise a realistic boundary, not merely name an unrelated
topic. Add fixtures in the same change as a component or trigger description.

These fixtures are reviewable routing hypotheses. Static validation proves only
coverage and basic fixture hygiene; it does **not** prove that GitHub Copilot,
Claude Code, or any other model will route those prompts as intended.

## Retrieval route and composition contracts

`retrieval-scenarios.json` is a schema-versioned, model-free contract corpus for
the routing decisions documented by `retrieval-core`. It keeps three layers in
one reviewable file:

- `routes` declares every retrieval modality and non-retrieval escalation, its
  owning plugin, and the tools that scenarios may reference;
- `compositions` declares named, ordered route-step variants; and
- `scenarios` provides a stable ID, natural-language query, corpus cues, expected
  primary route, exact composition steps when applicable, participating plugins
  and tools, rationale, and at least one realistic near miss.

The validator requires exact coverage of the documented route and composition
IDs and at least one scenario for every declared composition step variant. It
rejects unknown or missing routes, compositions, plugins, and tools; composition
steps that do not match a declared variant; plugin lists that do not match the
participating routes; weak or duplicate queries; uncovered contracts or
variants; and near misses that do not cross a routing boundary. Plugin references
must resolve to shipped plugin manifests.

This is a **static contract suite**. Passing means the corpus is internally
consistent and completely covers the documented routing surface. It does not run
an agent, score a model response, or measure routing accuracy.

### Add or change a scenario

1. Choose the documented route or composition boundary being exercised.
2. Add a unique kebab-case scenario ID, a query, concrete corpus cues, and a
   concise rationale.
3. Set `expected.route` to the first route used. For a composition, copy one
   declared `step_variants` sequence exactly into `expected.composition.steps`.
4. List participating plugins in first-use order and select only tools declared
   by those routes. The validator checks both references.
5. Add a near miss whose expected primary route differs, or whose query needs
   only the primary route rather than the parent scenario's composition.
6. Run both catalog-quality commands above. When adding a newly documented route
   or composition, update the validator's required contract set and add at least
   one    primary scenario for every declared variant in the same change.

## Agent output contracts

Agents with a formal response shape use an explicit Markdown section marker.
The preferred marker is `## Output contract`; the existing `## Report` marker is
also recognized. Every detected marker must have a matching
`agent_output_contracts` policy entry naming the exact marker and stable required
terms. The validator checks that the section exists, is non-empty, and retains
those terms.

Agents without a formal response contract do not need a marker. Add a policy
entry whenever a new contract section is introduced.

## Workflow smoke test

`tests/smoke-plan-workflow.mjs` evaluates the existing
`plan-big-execute-small.workflow.js` with Node's standard library and injected
mocks for `agent`, `parallel`, `phase`, and `log`. It exercises the successful
four-phase path, the empty-plan path, and invalid input while replacing `fetch`
with a function that fails immediately. It checks orchestration and result shape
without making model or network calls.

## Future live-model evaluation

Discovery fixtures and `retrieval-scenarios.json` can later feed a scheduled
live-model routing evaluation. The retrieval corpus already provides stable IDs,
queries, corpus cues, expected routes/compositions, and near misses; a future
runner should record provider/model/version and observed selections separately
rather than writing results back into the contract file.

Keep that job credentialed, rate-limited, and **non-blocking** because model
routing is probabilistic and provider behavior changes. Store trend data and
review regressions rather than turning stochastic results into a pull-request
gate. Deterministic policy, fixture, and retrieval-contract checks remain the
blocking CI contract.
