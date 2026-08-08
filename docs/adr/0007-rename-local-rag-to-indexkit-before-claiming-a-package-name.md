---
schemaVersion: 0.1.0
id: "0007"
title: "Rename local-rag to indexkit before claiming a package name"
status: accepted
date: 2026-08-08
deciders: ["@mbeacom"]
tags: [naming, packaging, local-rag, indexkit, migration]
scope: org
reversibility: one-way-door
blastRadius: cross-team
relatesTo: ["0002", "0005", "0006"]
affects:
  - type: path
    pattern: plugins/indexkit/**
  - type: path
    pattern: plugins/memory/**
    note: Resolves the engine as a marketplace sibling by directory name.
  - type: path
    pattern: plugins/obsidian/**
    note: Delegates queries to the engine CLI.
  - type: package
    pattern: indexkit
    note: PyPI and npm name claimed at first publish. Both unclaimed 2026-08-08.
provenance:
  authoredBy: agent-drafted
  ratifiedBy: "@mbeacom"
  agent:
    name: Copilot CLI
    model: claude-opus-5
    harness: github-copilot-cli
---

# ADR-0007: Rename local-rag to indexkit before claiming a package name

## Context

ADR-0006 decided to publish the retrieval engine and flagged naming as a
prerequisite rather than a follow-up: the first publish claims a PyPI name
effectively permanently, so the name must be settled before release, not
discovered after it.

The existing name has three concrete defects.

**"local" is falsifiable in a supported configuration.** `embed.py` accepts a
configurable `host`, and `CONTEXT_KIT_OLLAMA_HOST` is documented. Point the tool
at a remote ollama — which we support — and the name is false. This is the same
defect class the name was presumably chosen to avoid: it encodes a deployment
property rather than a capability.

**"RAG" understates the tool.** Its own description reads "Local semantic and
hybrid RAG: ollama, turbovec, and SQLite FTS5/BM25." It performs lexical
BM25 retrieval alongside semantic search. RAG names one architecture; the tool
implements a hybrid of two retrieval modalities.

**The name is not internally consistent.** Four surfaces disagree: the PyPI
package (`local-rag`), the console script (`local-rag`), the CLI `prog`
(`rag`), and the executable shim (`bin/rag`).

Two candidates were evaluated. Both are unclaimed on PyPI and npm, and both have
only trivial GitHub collisions, so availability did not decide it.

`groundkit` names the outcome — grounding output in real sources — and
outcome-names generally age better than artifact-names. An initial objection,
that "grounding" would collide with the `verify` plugin's vocabulary, was tested
against the corpus and largely did not hold: the only substantive occurrence is
`verifier.md` using the stock phrase "ground truth."

The argument that decided it is different. **Grounding is what the entire
catalog does.** `code-search`, `memory`, `obsidian`, and `retrieval-core` all
exist to put the right information in front of an agent. Naming one component
`groundkit` assigns the category's name to a single member, leaves nothing to
call its siblings, and sits awkwardly beside the `context-kit` umbrella it would
nearly duplicate. That is the same failure as `local-rag` — naming a category
rather than a product.

What distinguishes this component within the family is that it **builds and
maintains a persistent index**, where `code-search` scans live. Four of its five
commands (`index`, `status`, `list`, `remove`) are index lifecycle; only `query`
is retrieval.

"Index" also survives the test that condemns "local": turbovec is the mechanism,
but the *index* is the user-facing domain model. Replacing the vector store
leaves indexes intact, whereas "local" is falsified by a single environment
variable.

## Decision

We will rename the plugin, Python package, module, and CLI from `local-rag` to
**`indexkit`**, unifying all four naming surfaces on one name, before the first
package is published.

The rename ships with backward compatibility: previously documented
`CONTEXT_KIT_LOCAL_RAG_*` environment variables continue to be read as
fallbacks, `memory`'s sibling-directory resolution accepts either directory
name, and the `rag` memory-provider identifier remains accepted so existing
configuration does not break.

## Options considered

### Option A: Rename to `indexkit` now, before publishing (chosen)

| Dimension | Assessment |
|---|---|
| Name accuracy | Honest about hybrid retrieval; no locality claim |
| Family fit | Matches `adrkit`; clearly a component, not the umbrella |
| Timing | Before a permanent PyPI claim |
| Cost | ~300 occurrences across 68 files; existing plugin installs break |

### Option B: Rename to `groundkit`

**Pros:** Names the durable outcome rather than the artifact; ages better if the
implementation changes; slightly cleaner GitHub namespace.
**Cons:** Duplicates the category and the `context-kit` umbrella, leaving its
sibling retrieval plugins unnamed by the same logic.

### Option C: Keep `local-rag`

**Pros:** Zero migration cost. Real discoverability: "local RAG" is close to
verbatim what a prospective user searches for.
**Cons:** Preserves a name falsifiable by a supported setting, understating a
hybrid engine, across four inconsistent surfaces. The discoverability benefit is
substantially recoverable through PyPI `description` and `keywords`, which are
indexed by search.

### Option D: Publish first, rename later

**Cons:** Inverts the one-way door. A published name is sticky, and renaming
after release strands installs and splits the package's history.

## Trade-offs

- **Existing plugin installs break.** A plugin rename is not a version bump; per
  ADR-0005 the version is a cache key, but the *name* is the identity. Users
  with `local-rag` installed must install `indexkit`. Environment-variable and
  provider-identifier compatibility reduce, but do not eliminate, this.
- **We lose a high-intent search term.** "local RAG" is what the audience types.
  Keywords mitigate this; they do not fully replace a name match.
- **A large mechanical diff** touching ~68 files raises the chance of a missed
  reference, particularly where "rag" legitimately means the technique rather
  than this tool.
- **"Index" is a common word.** The compound carries the distinctiveness; the
  bare noun does not.

## Consequences

- **Easier:** one name across package, script, module, and CLI; a name that
  stays true under remote embedding hosts and future retrieval modes.
- **Harder:** a migration for existing users, and one more compatibility surface
  to maintain until the fallbacks are retired.
- **How we would know this was wrong:** post-publish, installs are negligible
  while inbound references keep arriving for "local rag" — indicating the name
  change cost more discovery than the accuracy gained. Measurable after release.
- **Revisit if:** the tool stops maintaining persistent indexes, which would
  falsify `index` the way remote hosts falsified `local`.

## Action items

1. [ ] Rename directories, module, CLI, and shim; unify all four surfaces.
2. [ ] Keep `CONTEXT_KIT_LOCAL_RAG_*` readable as a documented fallback.
3. [ ] Keep `memory` sibling resolution working for both directory names.
4. [ ] Put "local RAG", "offline", and "hybrid retrieval" in package keywords.
5. [ ] Note the migration in the plugin `CHANGELOG.md`.
