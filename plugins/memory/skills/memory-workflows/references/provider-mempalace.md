# MemPalace Provider

[MemPalace](https://github.com/MemPalace/mempalace) is an optional external
provider. It contributes local-first verbatim storage, project/topic structure,
hybrid retrieval, neighboring context, and host integrations. `context-kit`
does not vendor or import its Python internals.

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
python3 "$MEMORY" archive-handoff .context-kit/handoff.md
```

`capture` and `archive-handoff` always preserve an exact local copy first.
When the provider is enabled, the adapter then invokes MemPalace with exact argv
and no shell. Use `--local-only` to skip provider archival.

## Boundaries

- Do not index a repository in both MemPalace and `local-rag` by default.
  `local-rag` owns corpus RAG; MemPalace owns opt-in durable session/project
  recall.
- Do not enable a writable MCP server automatically. Configure MemPalace MCP
  separately, preferably read-only for recall-only clients.
- Do not use a global knowledge graph for project facts.
- Treat MemPalace output as retrieval candidates. Re-open original sources before
  acting on consequential claims.
- Provider upgrades may change CLI behavior. Run `doctor` and the plugin tests
  before rollout.
