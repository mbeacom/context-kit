# Changelog

## 0.5.2 — 2026-08-08

- Make the governance modality reachable. The runner resolved `adr` only via
  `PATH`, while every documented way to run adrkit in this repository goes
  through `npx` — which installs nothing. A contributor following the docs got
  `unavailable` permanently, and because `unavailable` is the *correct* quiet
  answer, nothing surfaced it. `CONTEXT_KIT_ADR_BIN` now names an already-installed
  executable (a project-local `node_modules/.bin/adr` works), and the
  `unavailable` payload states the remedy instead of only the absence.
- Reject an `npx` fallback, deliberately. `npx --yes` contacts the registry on
  every invocation even with a pinned version and a warm cache, so it would
  falsify these operations' offline contract, turn the runner into a fetcher of
  registry code mid-analysis, and surface network failure as npm's exit code
  rather than as `unavailable`. A set-but-unusable `CONTEXT_KIT_ADR_BIN` is a
  refusal, never a silent fallback to `PATH` — including a variable set to
  nothing, since absent and blank are different states and reading blank as
  "unset" would resolve a different binary than the one configured.
- Calibrate governance rather than only enabling it: a governing record is a
  finding only when it changes the conclusion, an empty `declared` list on a
  large file is indeterminate (inline markers are scanned only within a bounded
  window, and `markers.truncated` cannot distinguish "none" from "missed"), an
  all-`accepted` corpus has not yet exercised the rejected-options value, and a
  corpus no always-on instruction file points at is never queried at any size.
- Fix a governance test that passed for the wrong reason. Its `assertIn("adr", …)`
  matched `docs/adr` in the *missing-corpus* message, so it never reached the
  missing-tool branch it claimed to cover.

## 0.5.1 — 2026-08-08

- Preflight the ADR corpus directory for governance operations. adrkit exits 2
  when `--dir` is missing and this runner reserves 2 for policy refusal, so a
  repository without `docs/adr` reported a refusal instead of the required
  `unavailable`. A missing corpus is now an unreached modality, never a finding.
- Make governance reachable from `change-impact/SKILL.md` itself — tool boundary,
  modality table, and the analysis flow — rather than only in progressive detail,
  so the main workflow cannot complete without considering it.
- Assert the governance read-only guarantee at the argv level. The prior test
  matched operation-id substrings, so repointing a builder at `adr new` would
  still have passed; verified by mutation.

## 0.5.0 — 2026-08-08

- Add a `governance` modality to the enforced inspection runner (ADR-0003):
  `adr-explain-path` and `adr-check-path` reach adrkit's read-only `explain`
  and `check` verbs as exact argv. Structural and historical evidence cannot
  say what the team already decided or rejected; this can.
- adrkit stays optional. A missing `adr` binary exits `unavailable`, so the
  modality is reported as unreached rather than silently skipped — an absent
  corpus is not evidence that no decision governs a path.
- Only read-only verbs are catalogued, and a test asserts the writing verbs
  (`new`, `migrate`) never enter a catalog whose contract is non-mutating.
  The caller-supplied corpus directory is path-confined like any other path.

## 0.4.3 — 2026-08-04

- Shorten the `verifier` agent and `verify-before-trust` skill triggers to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.4.2 — 2026-08-03

- Shorten the discovery description(s) to free aggregate budget for the new
  `deep-review` components. Triggers and scope are unchanged; the catalog
  budget stays at 4096 characters rather than being raised.

## 0.4.1 — 2026-07-27

- Shorten the discovery description(s) to free aggregate budget for the new
  `corpus-review` components. Triggers and scope are unchanged; the catalog
  budget is fixed, so every addition competes for the same remainder.

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
