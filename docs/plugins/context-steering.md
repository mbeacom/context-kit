# context-steering

!!! abstract "Place guidance at the cheapest layer that still fires"
    A skill-only teaching plugin for deciding where guidance should live —
    always-on memory, path-scoped rules, on-demand skills, delegated subagents,
    MCP servers, or deterministic hooks — without turning every turn into a
    context-budget tax.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install context-steering@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install context-steering@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install context-steering@context-kit
    ```

## Components

| Component | What it is |
| --- | --- |
| **`context-budget`** skill | A decision matrix for placing guidance in always-on memory, path-scoped rules, skills, subagents, MCP servers, or hooks while keeping the always-on budget small. |
| **`examples/`** directory | Inert, copy-paste templates for path-scoped rules and Claude Code hook JSON — documentation examples, not active hooks or rules. |

## The idea

Project memory (`CLAUDE.md` / `AGENTS.md`) and installed skill *descriptions* are
always in the agent's working set. Every always-on token competes with the actual
task, so put guidance where it costs the least:

| Layer | Use for | Cost |
| --- | --- | --- |
| Always-on memory | short, durable, always-relevant rules | highest (always loaded) |
| Path-scoped rules | conventions for a specific area of the tree | loaded when that path is touched |
| On-demand skills | bulky know-how pulled in by task | loaded when relevant |
| Subagents | independent investigations in their own context | isolated |
| Hooks | deterministic enforcement | runs outside the model |

!!! note "Ships nothing active"
    `context-steering` installs **no** live hooks or rules. The `examples/` are
    templates you copy and adapt.

## At a glance

| | |
| --- | --- |
| **Category** | steering |
| **Provides** | 1 skill + inert examples |
| **Dependencies** | none |
| **License** | MIT |
