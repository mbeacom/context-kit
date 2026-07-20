# MemPalace Provider

[MemPalace](https://github.com/MemPalace/mempalace) is an optional external
provider. It contributes local-first verbatim storage, project/topic structure,
hybrid retrieval, neighboring context, and host integrations. `context-kit`
does not vendor or import its Python internals.

## Compatibility

This adapter is tested against **MemPalace 3.6.0** (the 3.6.x release line).
`doctor` never imports MemPalace internals; instead it parses `mempalace
--version` and probes the exact `--help` surfaces the adapter depends on
(`mine --help`, `search --help`, and `wake-up --help`) with bounded timeouts,
so upstream CLI drift is caught before synchronization, search, or wake runs
against changed argv or missing options.

| Installed version | `doctor` reports | Meaning |
| --- | --- | --- |
| `3.6.x` | `version_status: tested` | Verified against this adapter. |
| `< 3.6.0` | `version_status: older-than-tested` | Not the tested line; run `doctor` — required capabilities may still be present. |
| `> 3.6.x` | `version_status: newer-than-tested` | Not yet verified; run `doctor` before relying on it. |
| unparseable | `version_status: unknown` | `--version` output changed shape; run `doctor` and consider filing an issue. |

A version outside the tested line is **not** on its own a hard failure —
`doctor` only refuses when a required capability (`capture`, `search`,
or `wake`) is actually missing or incompatible. This avoids blocking
a working install solely on a patch/minor version mismatch, while still
refusing clearly when the CLI contract really has changed. Run
`python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor` after
any MemPalace upgrade or downgrade and read its `compatibility` section.

## Install and configure

Install MemPalace separately in an isolated tool environment:

```bash
uv tool install mempalace

export CONTEXT_KIT_MEMORY_PROVIDER=mempalace
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_HOME="$HOME/.local/share/context-kit/memory"
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"

python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
```

`CONTEXT_KIT_MEMPALACE_BIN` may point to an absolute executable when
`mempalace` is not on `PATH`.

## Isolation

The adapter assigns each configured project its own palace under:

```text
${CONTEXT_KIT_MEMORY_HOME}/providers/mempalace/<project-key>/palace
```

This deliberately avoids MemPalace's global default and prevents one project's
recall from searching another project's store. The adapter sets
`MEMPALACE_PALACE_PATH` only for the child process. `<project-key>` combines a
readable prefix with the SHA-256 of the exact configured project identifier, so
distinct identifiers cannot collapse onto the same filesystem path.

## Commands

```bash
MEMORY="$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py"

python3 "$MEMORY" capture record.md
python3 "$MEMORY" search "why did we change retry policy" --results 8
python3 "$MEMORY" wake
python3 "$MEMORY" review
python3 "$MEMORY" record-state retry-policy --review accepted \
  --reason "Evidence was reviewed."
python3 "$MEMORY" sync-provider            # safe dry-run plan
python3 "$MEMORY" sync-provider --apply    # explicit rebuild and swap
python3 "$MEMORY" archive-handoff .context-kit/handoff.md
```

`capture` and `archive-handoff` always preserve an exact local copy first.
Neither command writes to MemPalace. An accepted/current capture records a
durable `pending-sync` receipt; proposed or inactive capture records a distinct
not-eligible skip. Handoffs remain local historical evidence and are not placed
in the active memory provider. Run `sync-provider --apply` explicitly after an
eligible capture or any state change before provider-backed recall.

## Receipts and reconciliation

Every provider capture decision, skip, failure, and successful reconciliation
writes an immutable receipt below:

```text
${CONTEXT_KIT_MEMORY_HOME}/receipts/<project-key>/
```

Receipts contain the provider/version, project key, palace path, operation,
record or projection hash, timestamp, exact argv, outcome, and any backup path;
they never contain provider credentials.

`sync-provider` projects only accepted/current local records into a fresh
project-isolated palace. Its default is dry-run. On POSIX, `--apply` waits for
the staged MemPalace command to succeed, preserves the old palace as a visible
backup, then swaps the staged palace into place. Unsupported platforms refuse
apply rather than partially replacing a palace. After capture or a state
transition, reconcile before provider-backed recall; the adapter refuses provider search
until the live palace contains its matching staged projection marker. Historical
receipts are audit evidence only; they never authorize provider recall. The
marker also binds the complete local record/state ledger, so a capture or state
change requires a fresh explicit sync even if the active record set later looks
the same. After the success receipt is durable, reconciliation retains only the
immediately previous generated palace backup and removes older generated
backups.

## GitHub Copilot MCP (optional, separate from this adapter)

MemPalace 3.6 ships `mempalace-mcp`, a standalone MCP server. This is a
**separate integration path from the stdlib adapter above**: the adapter
above is what `capture`, `search`, `wake`, and `review` use; Claude hooks only
queue local payloads for explicit review. `mempalace-mcp` instead lets a host's
own agent (here, GitHub Copilot CLI) call MemPalace recall directly as MCP
tools. `context-kit` does not
auto-register, auto-install, or otherwise wire this up for you — set it up
explicitly if you want it.

1. Get the project-isolated palace path from `doctor`'s `compatibility.palace_path`
   field:

   ```bash
   python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
   ```

2. Register it as a **project-scoped** MCP server so it only loads for this
   repository, never through your personal `~/.copilot/mcp-config.json`.
   Copilot CLI loads workspace servers from `.mcp.json` or `.github/mcp.json`
   at the Git root automatically. Add (or hand-edit) one of those files:

   ```json
   {
     "mcpServers": {
       "mempalace": {
         "type": "local",
         "command": "mempalace-mcp",
         "args": ["--read-only", "--palace", "<palace_path from doctor>"],
         "tools": ["*"]
       }
     }
   }
   ```

   `--read-only` is enforced by `mempalace-mcp` itself: mutating tools are
   hidden from `tools/list` and refused at dispatch, not merely hidden by the
   client. Verify the exact flag surface for your installed version with
   `mempalace-mcp --help` before relying on it.

3. Optionally restrict which tools Copilot can call (client-side filter, on
   top of the server's own `--read-only` enforcement) by replacing `"tools":
   ["*"]` with an explicit list. Use `mempalace-mcp --help` to see available
   tool names for your installed version.

Do not use `copilot mcp add` for this project-scoped setup: it writes directly
to your personal `~/.copilot/mcp-config.json` and does not provide a `--json`
preview mode. Keep the hand-edited workspace file from step 2.

Never point `--palace` at a shared or global palace — always use the exact
project-isolated path `doctor` reports so MCP recall stays scoped the same
way the CLI adapter is scoped.

## Remote/team serving (advanced, separate deployment)

MemPalace 3.6 can also serve a palace over HTTP (`mempalace serve` /
`mempalace-mcp --transport http`) so a team can share one palace. This is an
**advanced, separately operated deployment** that `context-kit` does not
configure, provision, or connect to. The adapter and the Copilot MCP guidance
above assume a local, project-isolated palace only.

If your team deploys remote serving anyway:

- Require TLS on the whole path (`--tls-cert`/`--tls-key`, or terminate TLS
  in front of it — never bind a non-loopback address without one).
- Require authentication for every client (a bind token or equivalent);
  never pass an insecure-bind flag on a network-reachable host.
- Restrict recall clients to read-only access (`--read-only`); never expose
  the mutating surface to a shared/team endpoint.
- Treat this as a decision the team makes and operates explicitly, with its
  own change control — not something toggled on by installing this plugin.
- Consult `mempalace serve --help` and `mempalace-mcp --help` for your exact
  installed version before deploying; flag names can change between
  releases.

## Boundaries

- Do not index a repository in both MemPalace and `local-rag` by default.
  `local-rag` owns corpus RAG; MemPalace owns opt-in durable session/project
  recall.
- Do not enable a writable MCP server automatically. Configure MemPalace MCP
  separately (see above), always read-only for recall-only clients.
- Do not use a global knowledge graph for project facts.
- Treat MemPalace output as retrieval candidates. Re-open original sources before
  acting on consequential claims.
- Provider upgrades may change CLI behavior. Run `doctor` and the plugin tests
  before rollout, and read `doctor`'s `compatibility` section for exactly
  which capability, if any, changed.
