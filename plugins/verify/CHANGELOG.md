# Changelog

## 0.4.0 — 2026-07-25

- Add an enforced read-only inspection runner for `change-impact`
  (`scripts/run-impact-inspection.py`): a stdlib, no-shell executor with a
  fixed, plugin-owned catalog of read-only operations covering history (git
  log/show/diff/blame), structural (`git grep`), and structured-data (`jq`, and
  `yq` when installed). It builds each argv itself, validates and positionally
  substitutes parameters, confines paths to the analysis root, scrubs the
  environment of `GIT_*` redirection and pager-exec vectors, bounds output and
  runtime, and exposes `--list` for discovery.
- The runner never silently downgrades: an unknown operation, bad parameter, or
  path escape is refused (exit 2), and a missing tool is reported `unavailable`
  (exit 3) so the skill marks that modality unreached instead of quietly
  delegating to an unconstrained agent.
- Enforce the runner's documented non-POSIX refusal in code: `main()` validates
  the platform before any child is spawned, so a non-POSIX host yields a
  machine-readable refusal (exit 2) rather than a mid-run traceback.
- Harden against repository-local `.git/config`: environment scrubbing
  neutralizes only global and system config, so every git invocation now also
  pins the program-executing settings git reads from the analysis root's own
  `.git/config` — runner-owned, fixed `-c core.pager=cat -c core.fsmonitor=`
  overrides plus `--no-ext-diff`/`--no-textconv` on the diff-producing
  operations. `git-grep` also pins `--basic-regexp` so the documented pattern
  kind is enforced by the runner rather than left to the repository-local
  `grep.patternType`, the same class of repo-config gap. Withhold `HOME` from the
  child so no `~/.gitconfig` or `~/.jq` is autoloaded.
- Encode each accepted `field` segment as a JSON-quoted bracket key
  (`a.b` → `.["a"]["b"]`) instead of a bare dotted filter, so a hyphenated
  segment such as `release-name` addresses the literal key rather than being
  parsed by `jq`/`yq` as a subtraction, and a digit-leading segment such as `2fa`
  does not become a syntax error.
- Rewrite the `change-impact` tool-boundary section, report-contract disclosure,
  and `/analyze-impact` command to prefer the enforced runner for its modalities
  and to disclose code-intelligence — and YAML when `yq` is absent — as
  delegation-only or unavailable.
- Document the runner in `references/inspection-runner.md` and the enforced
  boundary in `docs/security.md`.

## 0.3.1 - 2026-07-25

- Require an artifact pointer for observation evidence. An observation with no
  durable artifact cannot be cited — evidence has to be independently
  inspectable. Such an attempt stays `unable-to-check` with `evidence (none)`,
  naming the attempted source and the artifact that would need capturing, so
  the `none` form covers "attempted, nothing citable" as well as "not
  attempted" and every outcome has exactly one valid form.
- Correct the escalation description in `verify-before-trust`, which said
  `/collect-runtime-evidence` runs only a pre-reviewed allowlist command ID a
  few lines above the escalation path it documents.
- Complete the `change-impact` runtime-observation row, which still described
  the escalation as allowlist-only.

## 0.3.0 - 2026-07-25

- Define the evidence forms `verify` owns: repository `path:line`, an
  observation form (an observation source plus an artifact pointer, where the
  source is `command-id=<allowlist key>` for the sanctioned runner or
  `tool=<approved tool>@<target>` for an approved optional-tool observation),
  and `none`. Dependents inherit these instead of widening the slot themselves.
- Close the `unable-to-check` dead end. `verify-before-trust`, the verifier, the
  checklist, and the change-impact report contract now name
  `/collect-runtime-evidence` as the escalation for an unresolved runtime claim
  when `runtime-evidence` is installed, and require the same claim to be
  reassessed here rather than gaining a parallel verdict set. The escalation
  stays optional; `verify` does not depend on its own dependent.
- Fix the `change-impact` tool declaration, which prescribed history and
  structured-data inspection it had no grant to perform. Rather than granting
  commands — a prefix-matched allowlist cannot express "read-only", since
  `git diff`/`git show` accept `--output=<file>`, `git grep` accepts
  `--open-files-in-pager=<cmd>`, and `yq -i` rewrites in place — the skill now
  states an explicit tool boundary and routes every non-lexical modality to
  `retrieval-strategist` or `code-search`.
- Make `verify-before-trust` prose host-neutral by describing read-only search
  and reading by capability instead of Claude-specific tool names.
- Stop implying that `change-impact` enforces a read-only boundary. Neither its
  own `allowed-tools` declaration nor delegation is an enforcement control:
  `allowed-tools` pre-approves a surface rather than denying the rest and is not
  portable across hosts, while `retrieval-strategist` declares unrestricted
  `Bash` and `code-search` declares `Bash(git:*)`/`Bash(yq:*)`. The skill now
  describes what is declared versus what is reached, points at the boundary map
  in `docs/security.md` for what actually governs execution, requires an
  inspection-only constraint on any delegation, and requires unreached
  modalities and delegate-gathered evidence to be disclosed in the report.

## 0.2.0 - 2026-07-18

- Add the read-only `change-impact` skill and `/analyze-impact` command for
  prospective blast-radius analysis.
- Define a progressive-disclosure report contract that maps direct dependents,
  symbols and call sites, runtime/config/data/schema surfaces, tests,
  docs/operations, compatibility risks, unknowns, and evidence.
- Reuse `retrieval-core` search modalities and the verifier verdict taxonomy,
  while keeping `plan-execute` optional for broad parallel coverage.
- Distinguish observed impact from inferred risk and unknowns, and make scoped
  negative evidence explicitly weaker than proof of absence.

## 0.1.1 — 2026-07-18

- Order the install snippets in the `verify-before-trust` skill GitHub Copilot →
  APM → Claude Code. Claude Code stays fully supported.

## 0.1.0 — 2026-07-18

- Initial release.
- Add the read-only `verifier` subagent for checking claim sets against the
  actual repository with per-claim verdicts and `file:line` evidence.
- Add the `verify-before-trust` skill for main-agent verification discipline.
- Compose with `retrieval-core` so verification can use the retrieval strategy
  spine to locate evidence efficiently.
