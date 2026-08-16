---
description: Promote an observed decision in durable memory toward a ratifiable adrkit ADR, checking first whether an existing record already governs or already rejected it.
argument-hint: <memory record id, decision statement, or the paths the decision governs>
---

Promote `$ARGUMENTS` from an **observation that a decision was made** into a
**draft ADR a human can ratify**.

If `$ARGUMENTS` is empty, ask which decision to promote. Do not scan memory and
pick one — choosing what becomes repository governance is the user's call.

## What this command may and may not do

This is the promotion path defined by ADR-0003, and its single hard rule is that
**ratification is a human act**. You may draft. You may never ratify.

Concretely, the record you write must carry `provenance.authoredBy:
agent-drafted` and must **not** carry `provenance.ratifiedBy`, and its `status`
must be `draft` or `proposed` — never `accepted`. adrkit enforces exactly this
pairing (`agent-accepted-requires-ratifier`): a machine-originated record cannot
reach `accepted` without a named human ratifier, and `adr lint` fails it. Do not
work around the rule by setting `authoredBy: human`; that is a false provenance
claim about who authored the record, and it is the one field the corpus cannot
reconstruct later.

A memory record and an ADR are also not the same object, so this is a
**promotion, not a migration**. Leave the memory record in place and unmodified.
It remains the evidence-bound observation; the ADR becomes the ratified decision.

## Steps

1. **Resolve the decision.** If `memory` is installed and `$ARGUMENTS` names a
   record, use `/recall-memory` or the `memory-workflows` skill to read it, and
   keep its `source` and `source_hash` — they become the ADR's evidence. If the
   decision was given as prose, say so in the draft rather than implying a record
   exists. If `$ARGUMENTS` names a record that is not `review: accepted`, stop
   and report it: an unreviewed observation is not ready to become governance.

2. **Determine the paths it governs.** These become `affects`. A decision that
   governs no path is usually not an ADR — reconsider before continuing.

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

5. **Scaffold the record.** `adr new "<title>" --status draft --dir <dir>`. This
   is the one step here that writes, and it writes a draft. Then fill in:
   - `affects` — one entry per governed path, `type: path` with a
     picomatch-style glob `pattern` and a `note` saying why that path is bound.
     Other valid types are `entity`, `package`, `resource`, `api`, and `data`;
     there is no `glob` or `service` type.
   - `provenance.authoredBy: agent-drafted`, plus the agent name, model, and
     harness. No `ratifiedBy`.
   - `relatesTo` — any record found in step 3 that is adjacent but not superseded.
   - `supersedes` and `status: superseded` on the **old** record only when the
     user explicitly decides to supersede it. Never supersede a record on your
     own initiative.

6. **Write the reasoning, not just the rule.** The rule already lives in the
   instruction files; the corpus exists for what they cannot hold. Fill Context,
   Options considered (**including the options rejected, and why** — this is the
   field that stops re-litigation), Trade-offs stated plainly, Consequences, and
   an explicit "how we would know this was wrong" with a revisit condition. An
   ADR whose Options section has one option is a rationalization, not a decision.

7. **Validate.** `adr lint --dir <dir>`. Exit `0` is clean; `1` means errors that
   must be fixed before handing it over.

## Report

Return: the decision promoted and its evidence; what step 3 found in each of the
three buckets; the threshold judgment from step 4; the record path written and
its `affects` entries; the lint result; and an explicit statement that the record
is **unratified** and names the human decision still required — who must ratify,
and what they are being asked to agree to.

If you stopped at a duplicate, a rejection, or the threshold, report that instead
and write nothing. Stopping is a successful outcome for this command.
