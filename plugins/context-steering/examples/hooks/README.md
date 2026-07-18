# Hook Examples

Hooks are deterministic event handlers. Use them when steering must not depend on the model remembering a prose instruction.

At a high level:

- `PreToolUse` runs before a tool call and can block it by exiting non-zero.
- `PostToolUse` reacts after a tool call, for example to format changed files.
- `UserPromptSubmit` and `SessionStart` can inject context at prompt or session boundaries.
- `Stop` can gate completion until required checks pass.

The JSON examples in this directory use the Claude Code hook shape: a top-level `hooks` object, an event name, and entries with a `matcher` plus command hooks. Other hosts, including GitHub Copilot-style environments, may expose analogous automation through different configuration files or CI tasks.

These files are examples to copy into your own repository. They are not active hooks shipped by this plugin.
