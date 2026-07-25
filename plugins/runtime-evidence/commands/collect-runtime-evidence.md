---
description: Collect controlled dynamic evidence for one runtime claim
argument-hint: <runtime claim>
disable-model-invocation: true
---

Collect runtime evidence for this atomic claim:

```text
$ARGUMENTS
```

If `$ARGUMENTS` is empty, request one runtime claim and stop.

Apply the `runtime-evidence` skill and delegate the collection to the
`runtime-investigator` agent. Begin only after static verification has explained
why the claim remains `unable-to-check`.

Require a user-supplied, pre-reviewed allowlist config and select an exact command
ID already present in it. Do not invent a command, alter configured argv, edit the
config, or use direct shell execution as a fallback.

When no reviewed command ID can represent the claim, the skill's approved
optional-tool path is the only alternative, and only when every condition in its
`references/optional-tools.md` holds — the claim requires that modality, the user
approved the interaction and target environment, and the host exposes the tool.
Otherwise stop and report the missing reviewed capability.

Return the claim, reproduction command ID — or `tool=<approved tool>@<target>` as
the observation source on that path — environment, observations,
artifact/output pointers, verdict-ready evidence, limitations, and cleanup
status. Then pass those facts to `verify` for its existing verdict taxonomy.
