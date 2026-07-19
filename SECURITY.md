# Security policy

## Supported versions

Security fixes land on the default branch and ship in the current marketplace
versions. Older cached or installed plugin versions do not have a separate
backport commitment. Before reporting a problem, reproduce it with the latest
catalog and plugin version when that can be done safely.

## Report a vulnerability

Use [GitHub private vulnerability reporting][report] for suspected security
issues. Do not open a public issue when a report could expose credentials,
private corpus content, an exploitable command configuration, or a working
bypass.

Include:

- the affected plugin, component, and version or commit;
- the host (GitHub Copilot CLI, APM, or Claude Code) and operating system;
- the expected and observed trust boundary;
- minimal reproduction steps and impact; and
- any safe logs or artifacts with secrets and private content removed.

This project does not publish a bug bounty or response-time guarantee. Ordinary
bugs without sensitive details belong in the public [issue tracker][issues].

## Repository-specific scope

Useful reports include reproducible problems in shipped context-kit content,
especially:

- bypasses of `runtime-evidence` exact-ID selection, config ownership checks,
  output bounds, or artifact protections;
- cross-project memory disclosure, unintended lifecycle capture, or provider
  isolation failures;
- handoff validation failures that incorrectly accept mismatched or stale task
  state as current;
- plugin hooks, scripts, workflows, manifests, or instructions that cross their
  documented permissions or data boundary; and
- supply-chain or install behavior specific to this marketplace.

Third-party tools such as Ollama, uv, MemPalace, ripgrep, Obsidian, APM, Claude
Code, and GitHub Copilot retain their own security boundaries. Report defects in
those tools upstream unless context-kit's integration introduces the exposure.
An agent suggesting an unsafe command is not by itself a vulnerability in this
repository; a reproducible shipped instruction or enforcement bypass may be.

See the [security and trust boundaries guide][guide] before enabling hooks,
remote services, runtime commands, or third-party providers.

[guide]: docs/security.md
[issues]: https://github.com/mbeacom/context-kit/issues
[report]: https://github.com/mbeacom/context-kit/security/advisories/new
