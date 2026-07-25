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

Apply the `runtime-evidence` skill. Begin only after static verification has
explained why the claim remains `unable-to-check`.

Prefer the runner path. When a user-supplied, pre-reviewed allowlist config is
available, select an exact command ID already present in it and delegate the
collection to the `runtime-investigator` agent. Do not invent a command, alter
configured argv, edit the config, or use direct shell execution as a fallback.

When no config exists, or none of its command IDs matches, the skill's approved
optional-tool path is the only alternative, and only when every condition in its
`references/optional-tools.md` holds — the claim requires that modality, the user
approved the interaction and target environment, and the host exposes the tool.
Run that path here rather than delegating it: a subagent's tool grant is fixed,
so a host-exposed browser, debugger, or container tool is not reachable inside
`runtime-investigator`. If no suitable tool is exposed, stop and report the
missing reviewed capability.

Return the claim, observation source — the reproduction command ID, or
`tool=<approved tool>@<target>` on the optional-tool path — environment,
observations, artifact/output pointers, verdict-ready evidence, limitations, and
cleanup status, using the field set for the path you took. Then pass those facts
to `verify` for its existing verdict taxonomy.
