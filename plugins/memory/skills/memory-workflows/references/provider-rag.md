# Rag Provider (first-party)

`rag` is the built-in memory provider. It gives **offline semantic recall over
accepted memory records** using this repository's own
[`indexkit`](../../../../indexkit) plugin, so semantic search does not depend
on any external *memory provider*. It is not dependency-free: embeddings come
from a locally running Ollama, and `indexkit` itself must be runnable — either
from the published package or from a venv the plugin bootstraps with `uv`. See
Requirements below.

`memory` declares a hard dependency on `indexkit`, so installing `memory`
through Claude Code, GitHub Copilot, or APM also deploys the retrieval engine.

## Why it exists

The local record store ships a lexical fallback: it substring-matches query
tokens against primary memories and cue anchors. That finds a record only when
you already know roughly how it was worded. `rag` adds meaning-based recall, so
"what did we decide about hammering the billing service" can retrieve a record
phrased "the payment gateway rate-limits bursty retries".

Semantic recall was previously reachable only through MemPalace. With `rag`,
MemPalace is genuinely optional rather than the only route.

## Requirements

| Requirement | Notes |
| --- | --- |
| `indexkit` plugin | Installed automatically as a dependency. |
| A runnable `indexkit` | Either `pip install indexkit` (the launcher finds it on `PATH`) or a bootstrapped venv. Claude Code **and GitHub Copilot CLI** build the venv on `SessionStart`; **APM does not**. |
| `uv` | Used only by the bootstrap, not by a packaged install. |
| `ollama` + an embedding model | `ollama pull nomic-embed-text`. Embedding is local by default. |

Storage and embedding stay on-device unless `CONTEXT_KIT_OLLAMA_HOST` points at
a remote server, in which case record text is submitted to that host.

## Runtime readiness

`doctor` checks readiness itself before probing the CLI, so an unusable runtime
is reported up front rather than surfacing later as an opaque launcher error:

```bash
python3 "$MEMORY" doctor --provider rag              # report readiness
python3 "$MEMORY" doctor --provider rag --bootstrap  # build the venv, then report
```

`doctor` reports `ready` for **either** runtime — it resolves the executable
first and only inspects the venv when nothing else can serve the command. A
`pip install indexkit` with no venv is therefore ready, and `--bootstrap` (which
needs `uv` and a clone) is the fallback for hosts that want the plugin's own
venv.

One asymmetry matters when a venv already exists: the launcher prefers it over
`PATH`, so a packaged install does **not** displace a stale venv. Rebuild a
stale venv rather than installing the package alongside it.

When no runtime is usable, `doctor` refuses with the exact command to run:

```json
{
  "runtime": {
    "status": "missing",
    "venv": "~/.claude/plugins/data/indexkit/venv",
    "bootstrap_command": "bash …/plugins/indexkit/scripts/bootstrap.sh"
  }
}
```

`status` is `ready`, `missing`, `stale`, `uv-missing`, or `unknown`. **`stale`**
means the venv was built from different `pyproject.toml` metadata — it would
otherwise run outdated code silently, so it is treated as loudly as a missing
one. `unknown` (indexkit not found as a sibling) does not block, since the
configured CLI may still work.

The probe also reports `venv_status` (`ready`/`missing`/`stale`) and `uv`
(`present`/`missing`) separately. `uv` only builds the venv, so a venv that is
already usable reports `ready` even when `uv` is absent; `uv-missing` is
returned only when the venv actually needs rebuilding and `uv` is unavailable
to do it.

The check applies only to the bundled `bin/indexkit` launcher. If you point
`CONTEXT_KIT_INDEXKIT_BIN` at your own executable, it manages its own runtime and is
not gated.

## Configure

```bash
export CONTEXT_KIT_MEMORY_PROVIDER=rag
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_HOME="$HOME/.local/share/context-kit/memory"
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
```

`doctor` resolves the executable, parses `indexkit --version`, and probes the exact
`--help` surfaces the adapter depends on (`index --help`, `query --help`),
refusing when a required option is absent. It never imports `indexkit`.

`CONTEXT_KIT_INDEXKIT_BIN` may point to an absolute `rag` executable. Otherwise the
adapter uses `rag` from `PATH`, then falls back to the sibling plugin launcher
at `plugins/indexkit/bin/indexkit` — so no `PATH` entry is required.

## Isolation

Each configured project gets its own store:

```text
${CONTEXT_KIT_MEMORY_HOME}/providers/rag/<project-key>/store/
```

The adapter sets `CONTEXT_KIT_DATA` to that directory **for the child process
only**, so one project's recall cannot search another's index. `<project-key>`
combines a readable prefix with the SHA-256 of the exact configured project
identifier.

Because `CONTEXT_KIT_DATA` normally locates the venv as well, the adapter also
sets `CONTEXT_KIT_INDEXKIT_HOME` to the real indexkit home. That variable
(indexkit >= 0.4.0) pins venv resolution while index data is redirected;
without it, `bin/indexkit` would look for a venv inside the memory store, miss
the bootstrapped one, and fall through to whatever `indexkit` is on `PATH` — or
fail outright when there is none.

## Commands

```bash
MEMORY="$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py"

python3 "$MEMORY" capture record.md
python3 "$MEMORY" record-state retry-policy --review accepted \
  --reason "Compared the saved evidence with the current retry policy."
python3 "$MEMORY" sync-provider            # safe dry-run plan
python3 "$MEMORY" sync-provider --apply    # explicit rebuild and swap
python3 "$MEMORY" search "why did we change retry behavior" --results 8
```

Reconciliation is identical to the MemPalace path: `sync-provider --apply`
materializes accepted/current records into a temporary projection, indexes it
into a staged store, writes a projection marker, and swaps atomically only
after `rag` succeeds. A backup is preserved and pruned on success.

`capture` never writes to the index. An accepted/current capture records a
`pending-sync` receipt; run `sync-provider --apply` before provider-backed
recall reflects it.

## Search results

Unlike MemPalace, whose output is streamed through unchanged, `rag` hits are
**bound back to records** before being returned. The projection materializes
each record as `<record-id>.md`, so every hit maps to exactly one record:

```json
{
  "provider": "rag",
  "records": [
    {
      "id": "retry-policy",
      "review": "accepted",
      "freshness": "current",
      "source": "src/http/retry.py",
      "source_hash": "…",
      "source_state": "verified",
      "score": 271.5,
      "retrieval_mode": "semantic"
    }
  ],
  "unmatched_hits": []
}
```

A hit that cannot be bound to a current record is reported in `unmatched_hits`
rather than dropped — it means the index is ahead of the ledger.

Results are still **candidate leads**. Open the cited source and compare its
hash and repository anchors before relying on a recalled claim.

## Failure behavior

| Situation | Behavior |
| --- | --- |
| Index not reconciled with accepted/current records | **Refuses.** Correctness gate; run `sync-provider --apply`. |
| `rag` missing, not runnable, or failing (for example `ollama` is down) | Falls back to lexical local search and annotates the result with `degraded_from`, `degraded_reason`, and `degraded_detail`. |
| Both stale *and* unavailable | **Refuses.** Reconciliation is checked first, so a stale ledger is never masked by a quiet fallback. |

The degraded result is explicitly labeled as lexical. It never presents itself
as semantic recall.

## `wake`

`wake` is **provider-neutral**. It builds a bounded, recency-ordered digest of
accepted/current records from the local store, so it performs no provider call
and returns the same digest under `none`, `rag`, and `mempalace`. Records are
the system of record and a provider store is a rebuildable projection of them,
so there is nothing a provider could add that the records do not already have.

See `automation.md` for using that digest to prime a session.
