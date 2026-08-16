---
description: Check a plan, design, or proposed change against the decisions that already govern the paths it touches, surfacing rejected and superseded records before work is delegated.
argument-hint: <plan file, design doc, issue, or description of the proposed work>
---

Check `$ARGUMENTS` against the repository's ratified decisions **before** any
work is delegated or any code is written.

If `$ARGUMENTS` is empty, ask for the plan, design document, issue, or change
description. Do not infer one.

This command is **read-only**. It does not edit the plan, write records, or
implement anything. Its output is an input to a human decision.

## Why this runs before execution, not after

A plan is cheapest to change while it is still a plan. The failure this prevents
is an agent confidently proposing an approach the team already considered and
refused, then defending it — because the refusal was never written anywhere the
agent could see. `adr explain` and `adr check` return `rejected` and `superseded`
records alongside governing ones precisely so a settled question can be closed
with a citation instead of re-argued.

## Steps

1. **Extract the paths the plan touches.** Files it names, modules it changes,
   packages it adds, APIs and data it alters. Be generous — a decision binds a
   path pattern, so a plan that only *reads* a governed path can still be
   constrained by the record that governs it. If the plan is prose with no paths,
   resolve them first (use `retrieval-strategy`, or `retrieval-strategist` when
   the plan is broad); a path-less check is not a check.

2. **Query the corpus.** Prefer the enforced `governance` operations of
   `verify`'s inspection runner (`adr-explain-path`, `adr-check-path`) through
   its `change-impact` skill, which guarantees read-only with no shell. Directly,
   the equivalents are:

   ```bash
   adr check <path> [<path>...] --dir <dir> --json    # the whole touched set
   adr explain <path> --dir <dir> --json              # one path, in detail
   ```

   `adr check` takes the changed-file set and returns `governing`,
   `activeProposals`, `history`, `changedRecords`, `markerScan`, and `findings`
   across all of them. `adr explain` takes exactly one path and adds
   `firedMatchers` (which `affects` entry matched) and `declaredBy` (which line
   declared an inbound `@adr` marker) — use it wherever you need to say *why* a
   record binds a path.

3. **Read the exit code correctly. This is the trap.** `adr check` exits `1` only
   when a **changed ADR record** has an error-severity finding, and `0`
   otherwise. It does **not** exit non-zero because the plan conflicts with a
   governing decision. Exit `0` therefore means *the corpus is valid*, never
   *the plan is approved*. Inbound `@adr` markers are context and are never exit-code
   authorities. The conformance judgment in step 4 is yours to make and state; no
   exit code makes it for you.

4. **Classify each governing record against the plan**, and cite the record id
   and the matcher that fired for every one:
   - **Conforms** — the plan is consistent with the record. Say which part.
   - **Conflicts** — the plan does what an `accepted` record forbids, or undoes
     what it requires. This blocks the plan. Either the plan changes, or the
     record is superseded by a human first — never silently worked around.
   - **Re-opens a settled question** — the plan proposes an option some record
     lists as rejected, or that a `rejected`/`superseded` record already
     represents. Quote the original reasoning and its revisit condition. If the
     condition is now met, say so: that is a legitimate case to supersede, and it
     is a human decision.
   - **Unaddressed** — a record binds a touched path and the plan neither honors
     nor mentions it. This is usually the most useful finding, because it is the
     one nobody knew to look for.

5. **Report unreached honestly.** If `adr` is unavailable, or the repository
   keeps no corpus, say the governance modality was **unreached** and stop. Do
   not report "no conflicts found". A corpus that was never consulted and a
   corpus that returned nothing are different states, and collapsing them turns a
   missing install into false assurance.

## Report

Return, in order:

1. The plan as understood, and the touched path set you derived.
2. A table: record id · title · status · matcher that fired · verdict from step 4.
3. **Blocking conflicts** — each with the record it violates and the two honest
   options (change the plan, or supersede the record with a human ratifier).
4. **Settled questions being re-opened** — with the original rejection reasoning
   and whether its revisit condition is met.
5. **Unaddressed governing records.**
6. Modalities unreached, and why.
7. An explicit bottom line: whether the plan may proceed as written, proceed with
   stated amendments, or requires a human governance decision first.

When `plan-execute` is driving the work, run this before delegating to
`execution-worker`, and carry the blocking conflicts and unaddressed records into
each worker brief — a worker with no governance context will re-introduce exactly
the constraint this check found.
