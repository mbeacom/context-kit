# Troubleshooting and lifecycle

Start with the host, then the plugin runtime, then the artifact or data path.
Avoid reinstalling everything before identifying which boundary failed.

## First-run checklist

1. Confirm the marketplace and plugin are visible to the host.
2. Confirm the plugin's required third-party tools are on `PATH`.
3. Confirm any portable data/config variables point where you expect.
4. Run the smallest read-only status or doctor command.
5. Inspect host/plugin errors before enabling hooks or runtime execution.

### Verify installation by host

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace list
    copilot plugin list
    ```

    If the catalog is stale:

    ```bash
    copilot plugin marketplace update context-kit
    ```

    See the [GitHub Copilot guide](GITHUB_COPILOT.md) for installation and
    portable configuration.

=== "APM"

    ```bash
    apm doctor
    apm view code-search
    apm audit --ci
    ```

    Use `apm targets` to confirm deployment targets. In CI, `apm install
    --frozen` refuses a missing or out-of-sync lockfile; `apm audit --ci` checks
    installed integrity and policy separately.

    See the [APM guide](APM.md) for target and lockfile behavior.

=== "Claude Code"

    ```bash
    claude plugin list --json
    claude plugin details code-search@context-kit
    ```

    In an interactive session, `/plugin` shows **Installed** and **Errors** tabs.
    Run `/reload-plugins` after installation; `claude plugin update` requires a
    restart before the new version applies.

If the plugin is present but a skill does not trigger, name it explicitly in
the request and inspect its plugin details/component inventory.

## Missing tools or hooks

Run the bundled search-tool inventory from a clone:

```bash
bash plugins/code-search/scripts/check-tools.sh
```

`rg` is required for `code-search`; most other search tools are optional.
Plugin installation does not install third-party CLIs.

GitHub Copilot and APM do **not** run Claude hooks:

- bootstrap `local-rag` manually;
- use explicit memory commands; and
- do not expect Claude lifecycle capture or `SessionStart` behavior.

Claude Code loads plugin hooks. Check the `/plugin` **Errors** tab when a hook
fails. `context-handoff` has no hooks, and `context-steering` ships only inert
examples.

## Local RAG

### `rag` is missing

For GitHub Copilot, APM, or manual use:

```bash
export CONTEXT_KIT_DATA="$HOME/.local/share/context-kit/local-rag"
bash plugins/local-rag/scripts/bootstrap.sh
export PATH="$PWD/plugins/local-rag/bin:$PATH"
rag list
```

If bootstrap reports that `uv` is missing, install uv and rerun it. The script
recreates the environment when the plugin's Python manifest changes. Claude Code
uses `CLAUDE_PLUGIN_DATA` as the fallback data root and runs this bootstrap from
its `SessionStart` hook.

### Ollama cannot be reached or the model is missing

```bash
ollama serve
ollama pull "${CONTEXT_KIT_EMBED_MODEL:-nomic-embed-text}"
```

Check `CONTEXT_KIT_OLLAMA_HOST`; it defaults to
`http://localhost:11434`. A remote value sends indexed chunks and query text to
that endpoint, so confirm the trust and transport decision before retrying.
Claude's fallback variables are `CLAUDE_PLUGIN_OPTION_OLLAMA_HOST` and
`CLAUDE_PLUGIN_OPTION_EMBED_MODEL`.

### The index is missing or uses another model

```bash
rag list
rag status --name notes
```

Use the same `--name` used at index time. A changed model with a different
embedding dimension is refused; select the matching model or create a new named
index and reindex the corpus.

### `--hybrid` reports that FTS5 is unavailable

`--hybrid` requires Python's SQLite build to include FTS5. `rag status` reports
the capability. Use semantic mode without `--hybrid`, or run local-rag with a
Python/SQLite build that includes FTS5. The command fails visibly rather than
silently changing retrieval modes.

### Data or permissions are unexpected

Named indexes live under `${CONTEXT_KIT_DATA}/indexes/<name>/`. Confirm the
resolved variable, directory owner, free space, and corpus read permissions.
Changing the data root makes existing indexes appear missing until you restore
the old root or reindex.

## Runtime evidence refusal modes

[`runtime-evidence`](plugins/runtime-evidence.md) uses these exit categories:

| Exit | Meaning | Action |
| --- | --- | --- |
| `2` | Pre-execution refusal | Fix invocation, config, ownership, command ID, cwd, or artifact collision; no command ran |
| `124` | Timeout | Inspect the report, process cleanup, and external side effects |
| `125` | stdout or stderr exceeded its cap | Inspect bounded artifacts and cleanup; raise a cap only after review |
| `126` | Process could not spawn | Check executable path, permissions, and environment |
| Other nonzero | Child exit, propagated | Diagnose the allowlisted command; do not relabel it as runner success |

Common exit-`2` causes are:

- Windows, which is refused before config access or process creation;
- missing `CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG`;
- config not owned by the current effective user or writable by group/others;
- malformed config, unknown fields, or an unknown command ID;
- a relative or nonexistent `--cwd`; and
- an existing `<run-id>.stdout`, `.stderr`, or `.json` artifact.

Every post-spawn outcome writes a JSON report. Allowlisting still does not prove
the child is side-effect-free.

## Handoff invalid, mismatched, or stale

| Exit | Classification | Response |
| --- | --- | --- |
| `1` | Invalid structure | Repair or regenerate; do not resume |
| `2` | Repository, branch, or base-ref mismatch | Reject as authoritative state; switch context intentionally or use another artifact |
| `3` | HEAD, merge-base, or clean/dirty state changed | Show every difference and reverify affected claims |

A different worktree path alone is informational when identity anchors match.
Do not copy saved current-value arguments merely to make validation pass.
Handoffs default to `.context-kit/handoff.md`; a relative
`CONTEXT_KIT_HANDOFF_PATH` resolves from the repository root.

## Memory scope, provider, and hooks

Set an explicit project and run the doctor before capture or recall:

```bash
export CONTEXT_KIT_MEMORY_PROJECT="owner/repository"
export CONTEXT_KIT_MEMORY_ROOT="/path/to/context-kit/plugins/memory"
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
```

| Symptom | Check |
| --- | --- |
| Missing or invalid project | Use a concrete `owner/repository`; there is no global fallback |
| Artifact repository mismatch | Capture under the matching project or correct the artifact provenance |
| MemPalace selected but unavailable | Install it separately or set `CONTEXT_KIT_MEMPALACE_BIN` to an absolute executable |
| Provider timeout or nonzero exit | Run `doctor`, inspect provider output, and verify the installed version |
| Recall source is unavailable or drifted | Open current repository evidence and reverify before acting |
| Claude automatic capture does nothing | Set provider, project, and `CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true`; hooks are Claude-only |
| Detached hook failure | Inspect `${CONTEXT_KIT_MEMORY_HOME}/logs/` |

`CONTEXT_KIT_MEMORY_PROVIDER=none` is a ready local mode; MemPalace is optional.
Unsetting `CONTEXT_KIT_MEMORY_AUTO_CAPTURE` disables future forwarding but keeps
existing records, provider data, pending files, and logs.

## Update safely

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace update context-kit
    copilot plugin update code-search@context-kit
    # Or: copilot plugin update --all
    ```

=== "APM"

    ```bash
    apm outdated
    apm update --dry-run
    apm update
    apm audit --ci
    ```

=== "Claude Code"

    ```bash
    claude plugin marketplace update context-kit
    claude plugin update code-search@context-kit
    ```

    Restart Claude Code after updating.

Review changed plugin components and third-party dependency behavior before
rollout. For APM, commit the reviewed `apm.yml` and `apm.lock.yaml` together.

## Uninstall and remove data

=== "GitHub Copilot"

    ```bash
    copilot plugin uninstall code-search@context-kit
    copilot plugin marketplace remove context-kit
    ```

=== "APM"

    ```bash
    apm uninstall code-search
    apm prune --dry-run
    apm prune
    apm marketplace remove context-kit
    ```

=== "Claude Code"

    ```bash
    claude plugin uninstall code-search@context-kit --prune
    claude plugin marketplace remove context-kit
    ```

    Use `--keep-data` when uninstalling a Claude plugin if its host-managed data
    must remain.

Removing a plugin or marketplace does not imply that every portable data root,
repository artifact, provider store, or APM deployment file was deleted. Back up
what you need, disable hooks first, then inspect these locations before applying
your own retention policy.

## Where state lives

| State | Default or configured location |
| --- | --- |
| Local RAG environment and indexes | `${CONTEXT_KIT_DATA}/venv` and `${CONTEXT_KIT_DATA}/indexes/`; Claude fallback `CLAUDE_PLUGIN_DATA` |
| Runtime evidence | `${CONTEXT_KIT_DATA}/runtime-evidence/` |
| Current handoff | `.context-kit/handoff.md` or `CONTEXT_KIT_HANDOFF_PATH` |
| Reviewed memory records | `${CONTEXT_KIT_MEMORY_HOME}/records/<project-key>/` |
| Archived handoffs | `${CONTEXT_KIT_MEMORY_HOME}/handoffs/<project-key>/` |
| MemPalace project store | `${CONTEXT_KIT_MEMORY_HOME}/providers/mempalace/<project-key>/palace/` |
| Memory pending hook payloads and logs | `${CONTEXT_KIT_MEMORY_HOME}/pending/` and `${CONTEXT_KIT_MEMORY_HOME}/logs/` |
| APM project state | `apm.yml`, `apm.lock.yaml`, `apm_modules/`, and deployed target directories |
| Host plugin cache/config | Host-managed; inspect the relevant host guide and CLI |

Return to the [cookbook](cookbook.md) once the first-run check passes.
