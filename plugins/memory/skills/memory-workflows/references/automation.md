# Opt-in Automation

The memory plugin declares Claude `Stop`, `PreCompact`, and `SessionEnd` hooks,
but the adapter exits without invoking a provider unless automatic capture is
explicitly enabled.

## Enable

```bash
export CONTEXT_KIT_MEMORY_PROVIDER=mempalace
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
python3 "$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py" doctor
```

All three settings are required. Missing provider or project configuration is a
visible refusal rather than a silent global fallback.

## Behavior

- `Stop` forwards the hook payload in the foreground with a bounded timeout.
- `PreCompact` forwards before context compression with a larger bounded timeout.
- `SessionEnd` first saves the payload to a mode-0600 pending file, then starts a
  detached worker so the host's short exit budget does not kill the final save.
- Detached worker errors are appended under
  `${CONTEXT_KIT_MEMORY_HOME}/logs/`.
- The provider palace is isolated by explicit project.

The adapter passes exact argv to a separately installed `mempalace` executable.
It does not evaluate shell text, install dependencies, or discover transcript
directories on its own.

## Host boundaries

Claude Code loads the plugin's `hooks/hooks.json`. GitHub Copilot and APM do not
run Claude hooks, so their default remains explicit capture. Configure a host's
native MemPalace integration only after applying the same opt-in, project
isolation, retention, and privacy decisions.

Disable automation immediately with:

```bash
unset CONTEXT_KIT_MEMORY_AUTO_CAPTURE
```

The local reviewed records remain available; only lifecycle forwarding stops.
