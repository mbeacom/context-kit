# Cookbook

These recipes compose plugins around a task rather than a component. Install
only the named entry plugin and its documented runtime peers; declared plugin
dependencies are pulled automatically. Use the
[plugin catalog](plugins/index.md) to inspect each chain.

Before a recipe can execute code or send text to a configured service, review
the [security and trust boundaries](security.md).

## Retrieve, then pin

**Use when:** you need an answer from code or documents, not merely a ranked hit.

**Plugins:** [`retrieval-core`](plugins/retrieval-core.md) plus the relevant
retrieval plugin, usually [`code-search`](plugins/code-search.md) or
[`local-rag`](plugins/local-rag.md).

1. State the corpus and what you know: exact token, code shape, symbol, history,
   schema path, or meaning.
2. Let `retrieval-strategy` choose the cheapest useful modality.
3. Narrow to candidate files or chunks.
4. Open the primary source and pin exact lines or offsets.
5. Separate the source-backed answer from remaining inference.

For semantic notes:

```bash
rag query "why was retry backoff changed?" --name notes --k 8 --json
rg -n "retry|backoff" path/from/result.md
```

**Done means:** the answer cites primary evidence, not only search snippets or
vector similarity.

## Graph, then rerank

**Use when:** vault links or tags provide a better candidate set than a global
semantic query.

**Plugins:** [`obsidian`](plugins/obsidian.md) and
[`local-rag`](plugins/local-rag.md).

1. Index the vault once with a stable name.
2. Produce candidate note paths from the Obsidian graph or a file-based fallback.
3. Pipe those paths to `rag query --allowlist -`.
4. Pin the winning note and heading with `rg` or a direct read.

```bash
export CONTEXT_KIT_OBSIDIAN_VAULT="/path/to/vault"
rag index "$CONTEXT_KIT_OBSIDIAN_VAULT" --name notes

# Graph-aware, when the official CLI and Obsidian are available.
obsidian backlinks file="Project X" |
  rag query "open risks" --name notes --allowlist -

# Portable file fallback.
rg -l '(^|\s)#decision' "$CONTEXT_KIT_OBSIDIAN_VAULT" |
  rag query "why did we choose X" --name notes --allowlist -
```

Claude's configured vault path remains available through
`CLAUDE_PLUGIN_OPTION_VAULT_PATH`, but `CONTEXT_KIT_OBSIDIAN_VAULT` is preferred
for portable shell profiles.

**Done means:** graph or tag scope is visible, semantic ranking is bounded to
that scope, and the final claim is pinned to note text.

## Verify, then observe

**Use when:** static repository evidence leaves one runtime claim
`unable-to-check`.

**Plugins:** [`runtime-evidence`](plugins/runtime-evidence.md), which installs
[`verify`](plugins/verify.md) and `retrieval-core`.

1. Decompose the claim and run read-only verification first.
2. Continue only if the exact runtime claim remains `unable-to-check`.
3. Review a pre-existing command ID in your user-owned allowlist. Check its
   executable, argv, working directory, credentials, network access, side
   effects, and cleanup.
4. Point the workflow at the config and a private artifact root.
5. Collect one bounded run, then return its observations to `verify`.

```bash
export CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG="$HOME/.config/context-kit/runtime-evidence.json"
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit"
```

```text
/collect-runtime-evidence The health endpoint reports the configured dependency state.
```

Do not invent a command ID, edit argv during collection, or fall back to direct
shell execution. Allowlisting constrains selection; it does not make the command
side-effect-free.

**Done means:** the final verdict distinguishes observed output, limitations,
artifact paths, cleanup state, and any inference.

## Verify, then hand off

**Use when:** another session must continue the current repository task.

**Plugins:** [`context-handoff`](plugins/context-handoff.md), which installs
`verify` and `retrieval-core`.

1. Verify facts that will change the next session's actions.
2. Record exact validation commands and results.
3. Write and validate the bounded handoff.
4. In the next session, resume through the validator rather than reading the
   file as trusted instructions.
5. Stop on mismatch; reverify affected facts on staleness.

```bash
export CONTEXT_KIT_HANDOFF_PATH=".context-kit/handoff.md"
```

```text
/write-handoff
/resume-handoff
```

`CLAUDE_PLUGIN_ROOT` is the Claude-provided fallback used internally to find the
validator; portable callers should resolve the installed plugin root explicitly.

**Done means:** the resume brief identifies trusted facts, invalidated or
uncertain claims, unresolved items, and the first safe next step.

## Recall, then verify

**Use when:** a prior decision, constraint, procedure, or episode may save
rediscovery time.

**Plugins:** [`memory`](plugins/memory.md), which installs the handoff and
verification chain.

1. Set the exact repository scope and run the provider doctor.
2. Recall candidates by primary memory and cue anchors.
3. Open the original evidence for every consequential candidate.
4. Compare source hash, repository, branch, HEAD, freshness, review, and
   supersession state.
5. Verify what is true now and label remembered context separately.

```bash
export CONTEXT_KIT_MEMORY_PROJECT="owner/repository"
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
```

```text
/recall-memory "why did we change retry policy?"
```

Claude can use `CLAUDE_PLUGIN_ROOT` when it supplies the installed plugin root.

**Done means:** memory accelerated discovery, but the answer rests on current
primary evidence.

## Plan, then execute

**Use when:** the task is broad enough to justify strong planning and scoped
parallel workers.

**Plugin:** [`plan-execute`](plugins/plan-execute.md).

1. Define the objective, boundaries, expected outputs, and validation.
2. Ask the planner to produce independent, bounded subtasks.
3. Give each worker only the context and permissions required for its subtask.
4. Recheck worker claims and incomplete results before synthesis.
5. Have the strong model own conflicts, risk decisions, and the final answer.

```text
/plan-big-execute-small Audit the authentication migration and produce a verified implementation plan.
```

The bundled workflow is Claude-specific and resolves through
`${CLAUDE_PLUGIN_ROOT}`. On another host, apply the same
`plan-execute-strategy` with that host's subagent/task mechanism. Delegation
changes cost and context shape; it does not reduce the permissions of a worker
whose task explicitly allows writes or execution.

**Done means:** every subtask has an owner and result, verification gaps are
visible, and the final synthesis is based on checked findings.

## Choose the next guide

- Installation or first-run failure:
  [Troubleshooting and lifecycle](troubleshooting.md)
- Component behavior and dependencies: [Plugins](plugins/index.md)
- Why these modalities compose: [Architecture](ARCHITECTURE.md)
