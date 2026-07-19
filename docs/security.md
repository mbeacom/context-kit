# Security and trust boundaries

`context-kit` combines instructions, local scripts, host plugins, and optional
third-party executables. Installation makes those components available to an
agent; it does not make every command, corpus, provider, or model output trusted.

For a suspected vulnerability in context-kit itself, use
[GitHub private vulnerability reporting](https://github.com/mbeacom/context-kit/security/advisories/new).

## Review before enabling

1. Install only the plugins needed for the journey.
2. Review each plugin's component inventory and source before installation.
3. Treat hooks, workflows, and commands as executable behavior, not as passive
   prompt text.
4. Review every third-party CLI and service with the same care as a direct shell
   command.
5. Choose data paths, retention, and access controls appropriate for the corpus.

The [plugin catalog](plugins/index.md) shows dependencies and links to the
canonical component pages. Host-specific installation remains in
[GitHub Copilot](GITHUB_COPILOT.md), [APM](APM.md), and
[Getting started](getting-started.md).

## Boundary map

| Surface | Trusted input or owner | Data and effects | Boundary that remains |
| --- | --- | --- | --- |
| Skills and agents | Installed plugin content plus the current host | Can recommend tool calls or delegate work | Host permissions and operator review still govern actual execution |
| Third-party CLIs | Executable resolved by the host environment | May read files, write files, use credentials, or access networks | Plugin installation does not audit or sandbox the executable |
| `local-rag` | Chosen corpus, data directory, embedding model, and Ollama endpoint | Stores chunks, metadata, and vectors; sends text to the configured endpoint | "Local" assumes a trusted local endpoint; a configured remote host receives corpus chunks and queries |
| `runtime-evidence` | User-owned allowlist mapping an exact ID to literal argv | Executes one selected process and writes bounded artifacts | Exact selection is not proof that the executable is safe or side-effect-free |
| `context-handoff` | Current repository identity and a validated artifact | Writes bounded task state with repository provenance | Saved claims must be rejected or reverified when identity or freshness anchors differ |
| `memory` | Explicit project scope, reviewed records, and optional provider | Persists evidence-backed records and may forward opted-in Claude hook payloads | Recall is a lead, not current truth; provider behavior and retention remain separate |
| APM | Project manifest, lockfile, policy, and deployed files | Resolves, deploys, hashes, and audits packages | Integrity and policy checks do not prove semantic safety or runtime harmlessness |

## Local RAG: endpoint and storage

[`local-rag`](plugins/local-rag.md) defaults
`CONTEXT_KIT_OLLAMA_HOST` to `http://localhost:11434`. Indexing sends each text
chunk to that endpoint, and querying sends the query text. If you point the
variable at another host, that server receives the submitted text; evaluate its
operator, transport, authentication, logging, and retention before indexing a
sensitive corpus.

Named indexes persist under:

```text
${CONTEXT_KIT_DATA}/indexes/<name>/
```

They include source text chunks and metadata in SQLite plus a vector index.
`local-rag` does not add encryption or a retention policy. Protect and delete
the directory using the controls of the account and filesystem that own it.
Claude Code may supply `CLAUDE_PLUGIN_DATA` as the fallback data root.

`--allowlist` narrows retrieval candidates; it is not an access-control system
for the underlying corpus or index.

## Runtime evidence: selection is not safety

[`runtime-evidence`](plugins/runtime-evidence.md) accepts an exact command ID
from a user-owned JSON config. The runner uses literal argv without a shell,
requires an absolute working directory, checks POSIX config ownership and
writable permissions, caps time and each output stream, and refuses artifact
overwrites.

Those controls limit *selection and capture*. The chosen executable can still:

- mutate files or external systems;
- read credentials or private data;
- access a network;
- create descendants; or
- require cleanup after timeout or failure.

Review those effects before adding an ID. Keep the config outside the installed
plugin, limit who can write it, and treat artifacts under
`${CONTEXT_KIT_DATA}/runtime-evidence` as potentially sensitive command output.
Host-level command policy is independent.

## Handoffs: provenance before authority

[`context-handoff`](plugins/context-handoff.md) records repository, branch,
HEAD, base ref, merge base, and clean/dirty state. A resume must:

- stop on invalid structure;
- reject repository, branch, or base-ref mismatches; and
- show HEAD, merge-base, or worktree-state staleness before reverifying claims.

The artifact contains task details and repository paths, so store
`.context-kit/handoff.md` (or `CONTEXT_KIT_HANDOFF_PATH`) according to the
project's sharing policy. The plugin has no lifecycle hooks and does not
automatically ingest handoffs into RAG or memory.

## Memory: scope, provider, and hooks

[`memory`](plugins/memory.md) requires an explicit
`CONTEXT_KIT_MEMORY_PROJECT=owner/repository`. Local reviewed records live below
`CONTEXT_KIT_MEMORY_HOME`, defaulting to
`~/.local/share/context-kit/memory`. The adapter rejects records whose repository
does not match the configured project.

`CONTEXT_KIT_MEMORY_PROVIDER=mempalace` delegates recall or archival to a
separately installed executable. The adapter gives each project a distinct
provider path and invokes exact argv without a shell, but MemPalace remains a
separate dependency with its own behavior. Run `doctor`, review upgrades, and
keep consequential recall tied to the original evidence and current repository.

Claude memory hooks ship disabled. Enabling
`CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true` forwards `Stop` and `PreCompact` payloads
in the foreground with bounded timeouts. `SessionEnd` writes a mode-0600 pending
file and starts a detached worker; detached-worker errors go to the memory log
directory. Make an explicit privacy, retention, and project-scope decision
first. Unsetting the variable stops forwarding but does not delete existing
records, pending files, or logs.

## Host and hook boundaries

- **Claude Code** loads plugin hooks. `local-rag` has a `SessionStart` bootstrap
  that creates or refreshes its uv environment; `memory` declares opt-in
  lifecycle hooks.
- **GitHub Copilot CLI and APM** install the shared plugin content but do not run
  Claude hooks. Bootstrap `local-rag` and capture memory explicitly.
- **`context-handoff`** has no hooks.
- **`context-steering`** ships inert hook examples only; copying one into an
  active host configuration is a separate operator action.

The uv bootstrap may resolve and install Python dependencies into the selected
data directory. Review the plugin source and dependency manifest before first
run, especially in restricted or offline environments.

## APM audit and install controls

APM adds a project manifest, lockfile, content hashes, target deployment, and
audit/policy checks. A security-conscious project flow is:

```bash
apm install --frozen
apm audit --ci
```

Use `apm update --dry-run` before changing locked refs. Treat findings as
integrity and policy signals, not a proof that prompts, scripts, or dependencies
are harmless. Flags such as `--force`, `--allow-insecure`, `--no-audit`, or
`--no-policy` weaken specific checks; use them only after reviewing the exact
reason and resulting exposure. See the [APM guide](APM.md) for package layout
and lifecycle details.

## Third-party command execution

Search, graph, document, model, and provider workflows can call tools such as
`rg`, `obsidian`, `ollama`, `uv`, or `mempalace`. Before allowing execution:

1. confirm the executable path and version;
2. inspect the arguments and working directory;
3. understand network, credential, filesystem, and subprocess behavior;
4. run with the least host permissions needed; and
5. inspect outputs before another agent treats them as evidence.

Continue with the [cookbook](cookbook.md) for bounded multi-plugin journeys or
the [troubleshooting and lifecycle guide](troubleshooting.md) for first-run
checks, refusal modes, updates, and data locations.
