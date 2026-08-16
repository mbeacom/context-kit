# adr-bridge

Bridges an [adrkit](https://github.com/mbeacom/adrkit) decision corpus to the
rest of `context-kit`: durable memory, planning, review, and semantic retrieval.

It deliberately does **not** teach you how to use adrkit. That knowledge belongs
with the tool that ships it — see [Scope](#scope-what-lives-here-and-what-does-not).

## Why

`context-kit` already reaches an ADR corpus in one place: `verify`'s inspection
runner exposes `adr explain` and `adr check` as enforced read-only `governance`
operations. That answers *"what governs this path?"* and nothing else.

Three questions were left unanswered, all of them named in
[ADR-0003](../../docs/adr/0003-treat-adrkit-as-a-peer-decision-corpus-not-a-memory-provider.md):

| Question | Command |
|---|---|
| This decision was observed in memory — should it become governance? | `/promote-decision-to-adr` |
| Does this plan violate something we already ratified, or revive something we rejected? | `/check-plan-against-decisions` |
| Have we decided anything about *X*, when I have no path to ask about? | `/index-decisions` |

Each is a **composition** that neither tool can own alone. adrkit does not know
`memory-v1` records, `execution-worker`, or `indexkit` exist; those plugins do
not know adrkit's schema. The bridge is the only place both are in scope.

## Install

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install adr-bridge@context-kit
```

Then make `adr` reachable. It is optional — every command degrades to a stated
`unreached` without it — but nothing here is useful until it resolves:

```bash
npm i -g @adrkit/cli@0.7.0          # provides `adr`
# or point at an existing install without a global:
export CONTEXT_KIT_ADR_BIN=./node_modules/.bin/adr
```

`CONTEXT_KIT_ADR_BIN` must name an executable that **already exists**; a package
specifier is refused rather than fetched. `npx` is never used, because these
operations are contracted read-only and offline and `npx --yes` contacts the
registry on every invocation.

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
manual on purpose: `provenance.ratifiedBy` is a human act, which adrkit enforces
by refusing `accepted` on a machine-authored record without a named ratifier.
`/promote-decision-to-adr` drafts; it never ratifies.

## Two failure modes worth stating

- **`adr check` exit `0` does not mean "plan approved."** It exits `1` only when
  a *changed ADR record* has an error finding. Conflict between a plan and a
  governing decision is a judgment you must make and state; no exit code makes it
  for you.
- **A semantic hit is a lead, not a ruling.** `status` is invisible to
  similarity, so a `rejected` record retrieved by `/index-decisions` reads exactly
  like an accepted one. Always resolve a hit back to its record and label the
  status in the citation.

## Scope: what lives here, and what does not

| Lives here | Lives in adrkit |
|---|---|
| Compositions referencing `memory`, `plan-execute`, `indexkit`, `verify`, `deep-review` | How to run `adr new` / `lint` / `check`, the frontmatter schema, ratification rules |

adrkit already ships `@adrkit/mcp` (a read-only, offline, no-LLM MCP server) and
`@adrkit/spec-kit` (`/speckit.adrkit.context`, `/check`, `/draft`). Duplicating
that here would fork the documentation and rot on adrkit's release cadence, not
this catalog's — it shipped 0.4.0 → 0.7.0 in about three weeks. Point agents at
adrkit's own MCP server for tool usage; use this plugin for the joins.

## Related

- `deep-review` ships a `conformance` lens charter that cites record ids and
  fired matchers, for reviewing an artifact against ratified decisions.
- `retrieval-core` routes the `decision-memory` modality and the
  `govern-then-change` composition.
- `verify`'s `change-impact` reports governance blast radius through the same
  corpus under an enforced read-only runner.
