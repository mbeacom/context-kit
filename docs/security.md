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
| `runtime-evidence` | User-owned allowlist mapping an exact ID to literal argv, or a user-approved optional tool when no command fits | Executes one selected process and writes bounded artifacts, or performs an approved browser/debugger observation the plugin does not bound | Exact selection is not proof that the executable is safe or side-effect-free; the optional-tool path is bounded by operator approval plus host policy, with nothing enforced by the plugin |
| `verify` | Plugin-owned catalog of read-only inspection operations; an analysis root supplied by the caller | Runs one selected read-only operation over history, structured-data, or `git grep`, with no shell, then reports bounded output | The catalog is read-only by construction, but the runner cannot prove the installed `git`/`jq`/`yq` is side-effect-free; code-intelligence and absent-`yq` YAML have no enforced operation and are reached only by disclosed delegation |
| `deep-review` | A caller-supplied artifact, frame, and lens charters | Reads the artifact and its surrounding context; writes findings, a ledger, and a report to a caller-chosen directory outside the findings dir | Lens workers read whatever their charter's evidence list allows; findings are judgment, and a `DEFECT` remains an unverified hypothesis until `verify` returns a verdict |
| `corpus-review` | A caller-supplied corpus root, scope rules, and review question | Reads corpus units and writes inventory, shard, findings, and report artifacts to a separate work directory | Reviewer workers read whatever the shard plan lists; scope rules are the only content boundary, and coverage numbers describe inspection, not sensitivity |
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

### The optional-tool path has weaker bounds

The allowlisted runner is not the plugin's only collection path. When no
reviewed command can represent a claim, an **approved optional-tool
observation** — browser, debugger, container inspector, or host-specific tool —
may be used instead. Understand how it differs before approving one:

| | Allowlisted runner | Optional tool |
| --- | --- | --- |
| What is pre-reviewed | exact argv, by ID | the interaction and target, by the user at approval time |
| Bounded by | the runner: timeout, per-stream output cap, no shell | operator approval plus host policy; nothing the plugin enforces |
| Runs in | `runtime-investigator`, instructed to invoke only the runner | the main agent, using host-exposed tooling |
| Artifacts | written by the runner, digest-anchored | at least one durable artifact the tool retained; a no-artifact attempt is not citable and leaves the claim `unable-to-check` |

The enforcing boundary on the first path is `run-evidence-command.py`, not the
subagent that calls it. `runtime-investigator` declares `Bash`, so its
command-only behavior is an instruction it follows, not a restriction its grant
imposes — host command policy governs that grant, as it does everywhere else in
this catalog.

This plugin ships **no collection mechanism** for the second path — only the
approval conditions and a recording contract. Enforcement is entirely the
host's and the operator's.

Treat it as the more consequential approval. A browser can mutate application
state through navigation, form submission, cookies, storage, and API calls, and
a debugger or container inspector can reach process memory, secrets, and live
data. Approve a specific interaction against a specific target, prefer
non-production environments, and expect no automatic cleanup: the plugin
records what was left behind rather than reversing it.

## Change-impact: enforced where it can be, disclosed where it cannot

[`verify`](plugins/verify.md)'s `change-impact` skill ships an enforced read-only
executor, `run-impact-inspection.py`, for the modalities where a declaration of
intent was not enough. Unlike `runtime-evidence`, its allowlist is not operator
review of a config file — the catalog of inspection operations is shipped in the
plugin's own code, so the read-only property is a property of that code. The
runner builds each argv itself from a fixed template, validates every parameter
by kind and positionally substitutes it, confines path parameters to the
caller-supplied analysis root, rebuilds the child environment to drop `GIT_*`
redirection and pager-exec variables (and to withhold `HOME`, so no `~/.gitconfig`
or `~/.jq` is autoloaded), caps time and each output stream, and never invokes a
shell. It also refuses to run at all on a non-POSIX host, where its capture and
process-group primitives do not port: the platform is validated before anything
is spawned, yielding a machine-readable refusal rather than a mid-run traceback.

That is an allowlist of permitted argument *shapes*, deliberately not a denylist
of bad flags — a denylist loses to the next tool release. Because no raw flag or
expression is ever accepted, the named write and exec vectors (`git`'s `--output`
write flag, `git grep`'s `--open-files-in-pager` exec flag, *caller-supplied*
`git -c` config injection, `yq`'s in-place flag) have no slot to land in. The
runner does use `-c` itself — fixed, runner-owned overrides that pin
program-executing config, never derived from a parameter — which is a distinct
thing from a caller reaching a `-c` slot, and that caller slot does not exist.

Environment scrubbing pins `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` to the null
device with `GIT_CONFIG_NOSYSTEM=1`, which neutralizes **global and system**
config only. Git still reads the analysis root's own repository-local
`.git/config`, which can define program-executing settings (`diff.external`, a
diff driver's `textconv`, `core.fsmonitor`). The runner therefore additionally
pins those on every git invocation — `-c core.pager=cat -c core.fsmonitor=` plus
`--no-ext-diff`/`--no-textconv` on the diff-producing operations. The same class
of repo-local override reaches `git grep`'s `grep.patternType`, which would
silently change the documented pattern kind; `git-grep` pins it with a fixed
`--basic-regexp`. A `field` parameter is likewise encoded as a bracket key
(`.["a"]["b"]`) rather than a bare dotted filter, so an accepted segment such as
`release-name` addresses the literal key instead of being read by `jq`/`yq` as a
subtraction or a syntax error.

What the runner enforces:

- only a shipped, plugin-owned operation runs; there is no config to edit;
- parameters are validated and positionally placed, never interpolated into
  flags, and paths stay inside the analysis root;
- no shell, so no metacharacter, glob, or substitution surface;
- a non-POSIX host is refused before any child is spawned.

What it does not establish:

- that the installed `git`/`jq`/`yq` binary is itself free of side effects;
- freedom from every repository-local `.git/config` program-executing setting:
  the runner pins the ones it knows, but a repo whose local config defines an
  unpinned diff driver could still reach it. `.git/config` is not
  clone-transferable, so this needs prior local write access to the repository,
  not merely cloning it;
- host command policy, which remains independent;
- coverage of code-intelligence, or of YAML when `yq` is absent.

The single most important property is that it **never silently downgrades**. An
unknown operation, malformed parameter, or path escape is refused (exit 2); a
missing tool is reported `unavailable` (exit 3). The skill then marks that
modality as unreached rather than quietly delegating to an unconstrained agent.
Delegation to `retrieval-strategist` or `code-search` remains available for
code-intelligence and as an *unenforced, disclosed* fallback for the runner's
modalities — a delegate's non-mutating behavior is an instruction it follows,
not a restriction its grant imposes, exactly as elsewhere in this catalog.

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
