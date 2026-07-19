# Optional Runtime Tools

The allowlisted runner is the default sanctioned execution path. Browser,
debugger, container, device, and host-specific runtime tools can add evidence
when the claim cannot be represented by a reviewed command.

## Use conditions

Use an optional tool only when all conditions hold:

1. The claim requires that observation modality.
2. The user has approved the intended interaction and target environment.
3. The current host exposes the tool.
4. The observation can be recorded with the same evidence fields: claim,
   environment, observations, artifact pointers, limitations, and cleanup.

## Graceful degradation

When a required optional tool is unavailable:

- Record the tool and capability that are missing.
- Leave the claim unsettled or retain `unable-to-check`.
- Suggest that the user provide a reviewed allowlist entry or run the observation
  in a host that exposes the tool.
- Do not invent a direct shell command, silently switch environments, or claim a
  static proxy proves the runtime behavior.

When a tool becomes unavailable after partial interaction, preserve the
artifacts already collected, state where the run stopped, and report cleanup
status explicitly.

## Browser-specific evidence

Record the URL/environment, viewport or device assumptions, user-visible state,
console/network observations when relevant, and screenshot/trace pointers.
Avoid treating visual appearance alone as proof of backend behavior.

Browser tools can mutate application state through navigation, form submission,
cookies, storage, and API calls. Apply the same side-effect review used for an
allowlisted command.
