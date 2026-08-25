# adr-bridge

Bridges an [adrkit](https://github.com/mbeacom/adrkit) decision corpus to the
parts only `context-kit` owns: durable memory and semantic retrieval.

It deliberately does **not** teach you how to use adrkit. That knowledge belongs
with the tool that ships it — see [Scope](#scope-what-lives-here-and-what-does-not).

## Why

`context-kit` already reaches an ADR corpus in one place: `verify`'s inspection
runner exposes `adr explain` and `adr check` as enforced read-only `governance`
operations. That answers *"what governs this path?"* and nothing else.

Two questions were left unanswered, both named in
[ADR-0003](../../docs/adr/0003-treat-adrkit-as-a-peer-decision-corpus-not-a-memory-provider.md):

| Question | Command |
|---|---|
| This decision was observed in memory — should it become governance? | `/promote-decision-to-adr` |
| Have we decided anything about *X*, when I have no path to ask about? | `/index-decisions` |

Each is a **composition** that neither tool can own alone. adrkit does not know
`memory-v1` records or `indexkit` exist; those plugins do not know adrkit's
schema. The bridge is the only place both are in scope.

For generic decision context, plan checking, ADR drafting, and queue review,
install adrkit's own portable agent plugin. It ships the `decision-memory` skill,
the `decision-checker` agent, and `/adr-context`, `/adr-check`, `/adr-draft`, and
`/adr-queue`.

## Install

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install adr-bridge@context-kit
```

Then make `adr` reachable. It is optional — every command degrades to a stated
`unreached` without it — but nothing here is useful until it resolves:

```bash
npm i -g @adrkit/cli@0.9.0          # provides `adr`
# or install project-locally and expose the same binary to every integration:
npm i --save-dev @adrkit/cli@0.9.0
export PATH="$PWD/node_modules/.bin:$PATH"
```

Putting the project-local binary on `PATH` makes it available to `verify`'s
governance runner, direct bridge checks, and adrkit's upstream commands. Setting
only `CONTEXT_KIT_ADR_BIN` configures the first of those, not the complete
workflow.

## The boundary this plugin keeps

A `type: decision` memory record and an ADR look alike and are not the same
object:

| | `memory` | adrkit |
|---|---|---|
| Records | Agent-observed, evidence-bound | Team-ratified, reviewed in a pull request |
| Lifecycle | Capture → review → accept | Propose → ratify → supersede |
| Enforcement | Recall-time | CI (`adr lint`, `adr check`) |
| Locatability | Cue anchors, semantic recall | `affects` patterns, inline `@adr` markers |

A memory record is an **observation that a decision was made**. An ADR is **the
decision, ratified**. They compose as a promotion path, and the promotion is
manual on purpose. `/promote-decision-to-adr` prepares the memory evidence and
governance context, adrkit's `/adr-draft` constructs and validates the proposed
record, and a human ratifies it.

## A failure mode worth stating

- **A semantic hit is a lead, not a ruling.** `status` is invisible to
  similarity, so a `rejected` record retrieved by `/index-decisions` reads exactly
  like an accepted one. Always resolve a hit back to its record and label the
  status in the citation.

## Scope: what lives here, and what does not

| Lives here | Lives in adrkit |
|---|---|
| Compositions referencing `memory` and `indexkit`, plus the `deep-review` conformance charter | Generic context/check/draft/queue workflows, CLI usage, schema, and ratification rules |

adrkit ships `@adrkit/mcp`, `@adrkit/spec-kit`, and a portable agent plugin.
Duplicating those here would fork the documentation and rot on adrkit's release
cadence, not this catalog's — it shipped 0.4.0 → 0.9.0 in about a month. Use
adrkit's plugin for the generic workflow and this plugin for the joins.

## Related

- `deep-review` ships a `conformance` lens charter that cites record ids and
  fired matchers, for reviewing an artifact against ratified decisions.
- `retrieval-core` routes the `decision-memory` modality and the
  `govern-then-change` composition.
- `verify`'s `change-impact` reports governance blast radius through the same
  corpus under an enforced read-only runner.
