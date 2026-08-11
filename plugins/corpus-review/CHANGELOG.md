# Changelog

## 0.1.4 — 2026-08-11

- **Fix: `corpus-reviewer` now registers on GitHub Copilot CLI.** Its `skills`
  frontmatter preloaded `corpus-review` as a comma-separated
  string, borrowing the `tools:` convention. Claude Code documents `skills` as a
  YAML list and tolerated the string; Copilot CLI validates it as an array and
  rejected the *entire* frontmatter (`skills: Expected array, received string`),
  so the agent loaded with empty metadata and never registered. Dispatching it
  failed with "agent type isn't registered", and callers silently fell back to a
  general-purpose worker — dropping the `tools` restriction this agent relies on.
  Now a YAML sequence, which both hosts accept. No behavior change on Claude Code.

## 0.1.3 — 2026-08-08

- Update retrieval references for the `local-rag` → `indexkit` rename (ADR-0007).

## 0.1.2 — 2026-08-04

- Shorten the `corpus-review` skill trigger to free aggregate discovery budget for the new
  `token-economics` components. Scope and routing are unchanged; the removed
  text was enumeration detail already covered in the skill body, and the
  catalog budget stays at 4096 characters rather than being raised.

## 0.1.1 — 2026-07-27

- Fix `/review-corpus` failing to load. Its `argument-hint: [corpus-root]`
  frontmatter was unquoted, so YAML resolved it to a flow sequence rather than a
  string and the host rejected the command with
  `argument-hint must be a string`.

## 0.1.0 — 2026-07-25

- Initial release: exhaustive review for a corpus too large to read in one
  context, as a distinct capability from retrieval.
- `corpus-review` skill: the frame → inventory → shard → dispatch → aggregate →
  report pipeline, the unit disposition vocabulary (`reviewed`, `partial`,
  `uninspectable`, `out_of_scope`, `failed`, `pending`), and the absence rule
  that `indeterminate` outranks `not-found` — a partially read, uninspectable,
  failed, or pending unit is never treated as evidence of absence.
- `corpus-reviewer` agent: a bounded per-shard worker with an output contract
  that reports its own coverage and uninspectable units alongside findings.
- `/review-corpus` command for the end-to-end run.
- `inventory-corpus.py` records directories it could not traverse and exits
  nonzero: `os.walk` ignores traversal errors by default, and a file that never
  enters the denominator cannot be reported as unread. `--allow-unreadable`
  accepts a known-incomplete denominator, which the ledger then reports and
  which blocks every `not-found` verdict.
- Presence is judged from Findings sections only, so a gap note such as "no
  incident report in this shard" no longer reads as proof the item was found.
- Shard digests cover path and range as well as content, so a same-content
  rename cannot resume onto findings that cite the old location.
- Aggregation rejects a report missing any contract section, treats an
  undecodable report as a failed shard rather than aborting the run, preserves
  each finding's continuation block into `findings.json`/`findings.md`, and
  serializes a per-unit ledger with the exact shards to re-dispatch.
- All three scripts refuse to write inside the corpus root.
- Standard-library scripts: `inventory-corpus.py` enumerates and hashes units,
  `plan-shards.py` produces a bounded shard plan with original-location anchors
  and a content-derived `inventory_sha256` that survives a re-inventory, and
  `aggregate-findings.py` merges findings into a coverage ledger that refuses to
  report completion while any unit is `pending` or `failed`, and refuses to emit
  an absence verdict when no unit was in scope.
- `findings.md` carries its own coverage caveat, so the standalone artifact
  cannot read as exhaustive when `partial`, `uninspectable`, or warning-bearing
  units mean most of the corpus went unread.
- References for the inventory contract, shard dispatch and resumability, and
  the coverage ledger.
