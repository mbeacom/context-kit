# context-steering

Context Steering is a skill-only teaching plugin for deciding where guidance should live: durable memory, path-scoped rules, on-demand skills, delegated subagents, or deterministic hooks. The aim is practical steering without turning every turn into a context-budget tax.

## Install

Claude Code:

```bash
/plugin marketplace add mbeacom/context-kit
/plugin install context-steering@context-kit
```

GitHub Copilot CLI:

```bash
copilot plugin marketplace add mbeacom/context-kit
copilot plugin install context-steering@context-kit
```

APM:

```bash
apm marketplace add mbeacom/context-kit
apm install context-steering@context-kit
```

## Components

| Component | What it is |
| --- | --- |
| **`context-budget`** skill | A decision matrix for placing guidance in always-on memory, path-scoped rules, skills, subagents, or hooks while keeping the always-on budget small. |
| **`examples/`** directory | Inert, copy-paste templates for path-scoped rules and Claude Code hook JSON. They are documentation examples, not active hooks or rules. |

## Why

Project memory and installed skill descriptions are always in the agent's working set. Put only short, durable, always-relevant guidance there; move bulky know-how to skills, area conventions to scoped rules, independent investigations to subagents, and deterministic enforcement to hooks.
