# Changelog

## 0.1.0 — 2026-08-15

Initial release. Bridges an [adrkit](https://github.com/mbeacom/adrkit) decision
corpus to the rest of the catalog, completing the integrations ADR-0003
anticipated but left unbuilt.

- **`/promote-decision-to-adr`** — the promotion path from ADR-0003 action item
  4. Turns a `type: decision` memory record (an *observation* that a decision was
  made) into a **draft** ADR a human can ratify. Checks `governing`,
  `activeProposals`, and `history` first, so a duplicate or an already-rejected
  option stops the command instead of entering the corpus. Never writes
  `provenance.ratifiedBy` and never sets `status: accepted` — adrkit's
  `agent-accepted-requires-ratifier` rule is treated as a property to uphold, not
  an obstacle to route around.
- **`/index-decisions`** — composes `indexkit` over the corpus so decisions are
  findable by meaning when no path is known, since `adr explain` is
  path-addressed. Requires every semantic hit to be resolved back to its record,
  because `status` is invisible to similarity: a `rejected` record argues its
  case in prose exactly as persuasively as an `accepted` one.

Design notes:

- **Commands only, by construction.** The catalog's aggregate discovery budget
  was at 4093/4096 characters when this plugin was written. Skills and agents
  consume that budget; commands do not. Governance work is also deliberate rather
  than ambient, so user-invoked commands are the honest surface.
- **Optional everywhere.** `verify` is the only dependency, for its enforced
  read-only inspection runner. `memory` and `indexkit` are used when installed
  and degrade to a stated `unreached` otherwise. A corpus that was never
  consulted and a corpus that returned nothing are different states.
- **No tool-usage skill or generic plan-check command.** adrkit ships its own
  portable `decision-memory` skill, `decision-checker` agent, and `/adr-context`,
  `/adr-check`, `/adr-draft`, and `/adr-queue` commands. This plugin only owns
  what references *this* catalog's plugins.
