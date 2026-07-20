# Opt-in Automation

The memory plugin declares Claude `Stop`, `PreCompact`, and `SessionEnd` hooks,
but the adapter exits without writing anything unless lifecycle queuing is
explicitly enabled.

## Enable

```bash
export CONTEXT_KIT_MEMORY_PROJECT=owner/repository
export CONTEXT_KIT_MEMORY_AUTO_CAPTURE=true
```

Both settings are required. A missing project is a visible refusal rather than a
silent global fallback.

## Behavior

- Each hook writes the exact JSON payload to a mode-0600 file under
  `${CONTEXT_KIT_MEMORY_HOME}/pending-hooks/<project-key>/`.
- Queued payloads are unreviewed evidence. They are never searched, converted
  into `memory-v1` records, or written to MemPalace automatically.
- Review the payload manually, create a durable record, run explicit `capture`,
  and then run `sync-provider --apply` if provider recall should change.
- Delete queued payloads under an operator-defined retention policy after
  review; they can contain sensitive session context.

The adapter does not evaluate shell text, install dependencies, or invoke a
provider from lifecycle hooks.

## Host boundaries

Claude Code loads the plugin's `hooks/hooks.json`. GitHub Copilot and APM do not
run Claude hooks, so their default remains explicit capture. Apply the same
opt-in, project isolation, retention, and privacy decisions to any host-native
lifecycle integration.

Disable automation immediately with:

```bash
unset CONTEXT_KIT_MEMORY_AUTO_CAPTURE
```

The local reviewed records remain available; only lifecycle queuing stops.
