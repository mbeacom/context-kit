# adr-bridge

`adr-bridge` joins an [adrkit](https://github.com/mbeacom/adrkit) decision
corpus to capabilities only `context-kit` owns. It does not duplicate adrkit's
portable `decision-memory` skill, `decision-checker` agent, or generic
context/check/draft/queue commands.

## Install

```bash
copilot plugin install adr-bridge@context-kit
# or
apm install adr-bridge@context-kit
```

Install adrkit's own agent plugin for ambient decision memory and the generic
workflow:

```bash
copilot plugin marketplace add mbeacom/adrkit
copilot plugin install adrkit@adrkit
```

Both plugins shell out to the `adr` CLI:

```bash
npm install -g @adrkit/cli@0.9.0
```

## Commands

| Command | Purpose |
|---|---|
| `/promote-decision-to-adr` | Prepare an accepted `type: decision` memory record as an evidence-and-governance handoff for adrkit's upstream `/adr-draft` |
| `/index-decisions` | Index the ADR corpus with indexkit, query it by meaning, then resolve each hit back to the authoritative record and status |

## Boundary

A memory record is an **observation that a decision was made**. An ADR is **the
decision, ratified**. The bridge leaves memory and the ADR corpus unchanged;
adrkit's `/adr-draft` constructs the proposed record, and a human ratifies it.

Semantic hits are leads, not rulings. Similarity cannot distinguish an accepted
record from a rejected one, so `/index-decisions` always resolves hits back to
the record's `status` and, when a path is known, its fired `affects` matcher.

See [ADR-0010](../adr/0010-split-adrkit-integration-between-a-context-kit-bridge-and-an-adrkit-hosted-tool.md)
for the ownership decision.
