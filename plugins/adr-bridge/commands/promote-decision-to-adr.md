---
description: Prepare an accepted memory decision for adrkit drafting by resolving its evidence, affected paths, and governing records, then hand it to upstream /adr-draft.
argument-hint: <memory record id, decision statement, or the paths the decision governs>
---

Promote `$ARGUMENTS` from an **observation that a decision was made** into a
**verified drafting handoff** for adrkit's `/adr-draft`.

If `$ARGUMENTS` is empty, ask which decision to promote. Do not scan memory and
pick one — choosing what becomes repository governance is the user's call.

## Ownership boundary

This bridge owns the context-kit-specific work: resolving a reviewed memory
record, retaining its evidence, identifying the paths it would govern, and
checking the existing decision corpus. adrkit's portable plugin owns record
construction, schema rules, validation, and ratification. Do not recreate those
rules here.

A memory record and an ADR are also not the same object, so this is a
**promotion, not a migration**. Leave the memory record in place and unmodified.
It remains the evidence-bound observation. `/adr-draft` may create a proposed
record from the handoff; only a human may ratify it.

## Steps

1. **Resolve the decision.** If `memory` is installed and `$ARGUMENTS` names a
   record, use `/recall-memory` or the `memory-workflows` skill to read it, and
   keep its `source` and `source_hash` — they become the ADR's evidence. If the
   decision was given as prose, label that explicitly rather than implying a
   record exists. If `$ARGUMENTS` names a record that is not `review: accepted`,
   stop and report it: an unreviewed observation is not ready to become
   governance.

2. **Determine the paths it governs.** Pass these paths and their rationale to
   upstream drafting. A decision that governs no path is usually not an ADR —
   reconsider before continuing.

3. **Check what already binds those paths — this is the step that earns the
   command.** For each path, run the `governance` operations of `verify`'s
   inspection runner (`adr-explain-path`, and `adr-check-path` where a change is
   in hand) via its `change-impact` skill, or `adr explain <path> --dir <dir>
   --json` directly. Read all three buckets:
   - `governing` — an `accepted` record already binds this path. If it says the
     same thing, **stop and report the duplicate**; do not write a second record.
     If it contradicts, this is a supersession, not a new decision (step 5).
   - `activeProposals` — a `draft`/`proposed` record is already in flight. Add to
     it rather than racing it.
   - `history` — `rejected`, `superseded`, and `deprecated` records. **A rejected
     record that matches the proposal is a stop condition.** Re-proposing a
     settled-and-refused option is the exact failure ADR-0001 created the corpus
     to prevent. Report the rejection and its reasoning; do not draft over it.

   If `adr` is unavailable, report the governance modality as **unreached** and
   stop before writing. An absent corpus is not evidence that nothing governs the
   path, and drafting blind is how a corpus acquires duplicates.

4. **Apply the ADR-0001 threshold.** Write a record only when the choice is hard
   to reverse, contested, or governs a path. Naming, formatting, and anything a
   future contributor can flip in one uncoordinated commit is not an ADR. Say so
   and stop rather than padding the corpus — a corpus that rots is worse than
   none, because it looks authoritative.

5. **Prepare the handoff.** Assemble:
   - the proposed title and decision statement;
   - the memory record id, `source`, `source_hash`, and accepted review state, or
     an explicit statement that the decision came from prose;
   - each path the decision would govern and why;
   - the ids, statuses, and relevant reasoning from `governing`,
     `activeProposals`, and `history`;
   - the threshold judgment from step 4; and
   - whether the user explicitly intends this proposal to replace an existing
     decision. Describe that as a candidate relationship only. Do not edit either
     record in this command.

6. **Hand off generic drafting.** Give that payload to adrkit's
   `/adr-draft "<title>"` command. Let the upstream command own CLI resolution,
   scaffolding, schema fields, supersession mechanics, and linting. Do not create
   or edit an ADR locally.

   If the host cannot invoke another command from this command, or adrkit's
   portable plugin is not installed, return the complete payload and the exact
   `/adr-draft "<title>"` next command. Mark drafting as **unreached** rather than
   substituting a local copy of adrkit's workflow.

## Report

Return: the decision and its evidence; what step 3 found in each of the three
buckets; the threshold judgment from step 4; the complete drafting handoff; and
whether `/adr-draft` was reached.

If upstream drafting completed, relay its record path, id, validation result, and
statement that the record remains unratified. If it was unreached, write no ADR.

If you stopped at a duplicate, a rejection, or the threshold, report that instead
and write nothing. Stopping is a successful outcome for this command.
