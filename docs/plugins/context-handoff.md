# context-handoff

!!! abstract "Bounded cross-session task state"
    Manually compile and resume verified task state with repository provenance.
    Validate identity and freshness before saved claims influence the next action.

`context-handoff` depends on [`verify`](verify.md), which transitively pulls
[`retrieval-core`](retrieval-core.md). Python 3 is required for its
standard-library validator.

## Install

=== "GitHub Copilot"

    ```bash
    copilot plugin marketplace add mbeacom/context-kit
    copilot plugin install context-handoff@context-kit
    ```

=== "APM"

    ```bash
    apm marketplace add mbeacom/context-kit
    apm install context-handoff@context-kit
    ```

=== "Claude Code"

    ```bash
    /plugin marketplace add mbeacom/context-kit
    /plugin install context-handoff@context-kit
    ```

## Manual-first workflow

```text
/write-handoff
/resume-handoff
```

Both commands accept an optional artifact path. Otherwise they use
`CONTEXT_KIT_HANDOFF_PATH`, then `.context-kit/handoff.md` under the repository
root. A relative override is also resolved from the repository root.

| Component | What it is |
| --- | --- |
| **`context-handoff`** skill | Portable compile/resume workflow and trust boundary. |
| **`handoff-compiler`** subagent | Read-only compiler that returns bounded structured Markdown to the caller; it never persists files. |
| **`/write-handoff`** | Gathers provenance, verifies important claims, writes the returned artifact, and validates it. |
| **`/resume-handoff`** | Validates structure and current identity/freshness, then reverifies stale claims before producing a resume brief. |
| **`validate-handoff.py`** | Deterministic stdlib validator with distinct invalid, mismatch, and stale statuses. |

The `context-kit/handoff-v1` artifact is capped at 32 KiB, 300 lines, and 25
top-level items per required section. It records scope, verified facts,
decisions, changed/completed work, unresolved items, next steps, validation
state, and repository provenance.

## Mismatch and staleness

- Repository identity, branch, or base-ref differences are **mismatches**. Resume
  rejects the artifact as authoritative task state.
- HEAD, merge-base, or clean/dirty-state differences are **stale**. Resume shows
  every difference and reverifies affected facts before use.
- A different worktree path is informational when identity anchors match.
- Malformed structure is invalid and must be repaired or regenerated.

!!! note "Authority and archival"
    Manual `/write-handoff` and `/resume-handoff` remain authoritative. The
    plugin has no lifecycle hooks, does not serialize hidden model state, and
    never automatically ingests artifacts. When separately requested, the
    [`memory`](memory.md) plugin can archive a validated handoff as historical
    evidence; resume must still freshness-check it.

## At a glance

| | |
| --- | --- |
| **Category** | continuity |
| **Provides** | skill, 2 commands, read-only subagent, stdlib Python validator |
| **Dependencies** | [`verify`](verify.md) → [`retrieval-core`](retrieval-core.md) |
| **License** | MIT |
