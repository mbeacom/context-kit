# Changelog

## 0.6.3 — 2026-08-15

- **Name `adr-bridge` as the reachable surface for the decision-memory
  modality.** The skill already routed the modality but named only adrkit itself
  and `verify`'s governance operations, so the composition commands were
  unreachable from routing. Also state the path-less case explicitly: with no
  path in hand, `govern-then-change` enters semantically over the corpus and then
  resolves each hit to its record, because `status` is invisible to similarity.

## 0.6.2 — 2026-08-11

- **Fix: `retrieval-strategist` now registers on GitHub Copilot CLI.** Its `skills`
  frontmatter preloaded `retrieval-strategy` as a comma-separated
  string, borrowing the `tools:` convention. Claude Code documents `skills` as a
  YAML list and tolerated the string; Copilot CLI validates it as an array and
  rejected the *entire* frontmatter (`skills: Expected array, received string`),
  so the agent loaded with empty metadata and never registered. Dispatching it
  failed with "agent type isn't registered", and callers silently fell back to a
  general-purpose worker — dropping the `tools` restriction this agent relies on.
  Now a YAML sequence, which both hosts accept. No behavior change on Claude Code.

## 0.6.1 — 2026-08-08

- Add decision/governance triggers to the skill and agent discovery descriptions.
  Hosts select components from those descriptions, so routing added only to the
  body left a "what governs this path?" request unable to activate either.

## 0.6.0 — 2026-08-08

- Route a **decision memory** modality (ADR-0003): whether something was already
  decided, what governs a path, and what was rejected — distinct from durable
  memory's agent-observed records, and reported as unreached when adrkit is absent.

## 0.5.3 — 2026-08-08

- Update modality routing for the `local-rag` → `indexkit` rename (ADR-0007).

## 0.5.2 — 2026-08-04

- Shorten the `retrieval-strategist` agent trigger to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.5.1 — 2026-08-03

- Shorten the discovery description(s) to free aggregate budget for the new
  `deep-review` components. Triggers and scope are unchanged; the catalog
  budget stays at 4096 characters rather than being raised.

## 0.5.0 — 2026-07-25

- Add the `corpus-review` route to the decision flow: when every unit must be
  accounted for and someone will act on what was *not* found, the task is
  exhaustive review rather than retrieval. Ranked hits cannot establish that
  nothing was skipped, so the strategist now routes those asks to
  `corpus-review` instead of presenting a retrieval result as complete coverage.

## 0.4.2 — 2026-07-25

- Update the "verify then observe" composition in both the
  `retrieval-strategist` agent and the `retrieval-strategy` skill: an
  unresolved runtime claim can escalate through `runtime-evidence`'s approved
  optional-tool path as well as its exact-ID allowlisted runner. Routing
  components described the runner as the only escalation, which could suppress
  the second path.

## 0.4.1 — 2026-07-19

- Document the deterministic retrieval contract corpus, its complete
  modality/route/composition coverage, and the explicit boundary between static
  validation and future non-blocking live-model evaluation.
- Add verify-then-observe and verify-then-hand-off to the operative strategy skill
  and agent so the enforced cross-plugin compositions are available in context.

## 0.4.0 — 2026-07-19

- Add durable memory as a distinct modality for prior decisions, constraints,
  procedures, preferences, and bounded episodes.
- Distinguish current task handoffs from long-term recall.
- Add recall-then-pin, recall-then-verify, and retrieve-then-expand compositions.
- Require source/freshness labels and current evidence when memory conflicts.

## 0.3.0 — 2026-07-18

- Route the new **code-intelligence** modality (symbol definitions, references,
  and call hierarchy) in the `retrieval-strategy` skill and `retrieval-strategist`
  agent, and add a "resolve then pin" composition (code-intelligence → `rg`).

## 0.2.6 — 2026-07-18

- Lead host guidance with GitHub Copilot, then APM, then Claude Code in the
  `retrieval-strategy` skill's portability note, and clarify that every host
  registers the marketplace before installing. Claude Code stays fully
  supported.

## 0.2.5 — 2026-07-18

- Rebrand: the marketplace was renamed `productivity-skills` → `context-kit`.
  Updated the `homepage`/`repository` URLs and install commands
  (`… install retrieval-core@context-kit`). GitHub redirects the old repository
  path, so existing marketplace registrations keep resolving.

## 0.2.4 — 2026-07-13

- Add an `apm.yml` manifest so Agent Package Manager (`microsoft/apm`) users can
  install this plugin (`apm install retrieval-core@context-kit`)
  alongside the Claude Code and GitHub Copilot flows. No `.apm/` directory, so
  the plugin-native layout stays authoritative.

## 0.2.3 — 2026-07-13

- Update GitHub Copilot guidance: Copilot CLI installs the plugin directly
  (`copilot plugin install`), replacing the manual `.github/skills` copy steps.

## 0.2.2 — 2026-05-29

- Document GitHub Copilot Agent Skills compatibility and how to adapt the
  `retrieval-strategist` agent to Copilot custom-agent frontmatter.

## 0.2.1 — 2026-05-28

- Note rtk in the strategy defaults and the strategist agent: prefer
  `rtk`-prefixed forms of wrapped commands (`rg`/`git`/`find`/`diff`) when installed.

## 0.2.0 — 2026-05-24

- Route into the semantic (indexkit) and graph (obsidian) modalities now that
  they ship; document hybrid rerank via `rag query --allowlist`.

## 0.1.0 — 2026-05-24

- Initial release: `retrieval-strategist` agent and `retrieval-strategy` skill.
