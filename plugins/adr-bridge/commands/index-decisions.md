---
description: Make an adrkit decision corpus semantically searchable with indexkit, so decisions can be found by meaning when no governed path is known, then resolved back to authoritative records.
argument-hint: "[question to ask the corpus, or 'index' to build or refresh the index]"
---

Make the repository's decision corpus answerable by **meaning** rather than only
by path, then resolve every hit back to the record that actually has authority.

## The gap this closes

`adr explain` and `adr check` are path-addressed: you must already know which
file you are touching. That is the right primitive for "what governs this
change?" and it is useless for the other half of the question — *"have we ever
decided anything about caching?"* — where no path is in hand and the record may
not use the word you are thinking of.

`indexkit` indexes markdown, and an ADR corpus is markdown with disciplined
frontmatter, so the two compose directly. The result is not a replacement for
`adr explain`; it is the entry point that finds the record whose path you then
explain.

## Steps

1. **Locate the corpus.** Default `docs/adr`; honor `--dir` if the repository
   keeps it elsewhere. If there is no corpus, say so and stop — nothing here
   applies.

2. **Index or refresh.**

   ```bash
   indexkit index docs/adr --name decisions
   ```

   Indexing is incremental, so re-run it after records land. Treat the index as a
   **projection that can be rebuilt**, never as the corpus: it holds no
   authority, and if it disagrees with the files, the files win.

3. **Query by meaning.**

   ```bash
   indexkit query "<question>" --name decisions --k 8 --hybrid
   ```

   Prefer `--hybrid` here. A decision corpus is dense with exact identifiers —
   record ids, path patterns, tool and package names — that pure semantic
   similarity blurs, and hybrid keeps the lexical half of the signal.

4. **Resolve every hit back to authority. This is the step that matters.** A
   semantic hit is a **lead**, not a ruling. Two failure modes make this
   non-optional:

   - **Status is invisible to similarity.** A `rejected` or `superseded` record
     argues its case in prose exactly as persuasively as an `accepted` one — that
     is what the Options and Context sections are *for*. Retrieved as a passage
     and read as guidance, a refused option becomes a recommendation. Always read
     `status` before quoting a record, and label it in every citation.
   - **A body is not a binding.** What a record governs is its `affects`
     patterns, not its prose. Matching text does not mean the record binds your
     change.

   So for each hit: open the record, read `status`, and where a path is in hand
   run `adr explain <path> --dir <dir> --json` to confirm whether it actually
   fires. `governing` holds only `accepted` records; `activeProposals` holds
   `draft`/`proposed`; `history` holds `rejected`, `superseded`, and
   `deprecated`.

5. **Narrow when the corpus is large.** Filter to a status bucket first, then
   pass the surviving paths as an allowlist so ranking happens only over records
   that can bind:

   ```bash
   <list of accepted record paths> | indexkit query "<question>" --name decisions --hybrid --allowlist -
   ```

## Reporting

Report each result as: record id · title · **status** · why it is relevant · and
whether it was confirmed to bind a path (with the matcher that fired) or is
context only. Never present a `rejected` or `superseded` record without its
status attached and, where it matters, the reasoning that retired it.

If `indexkit` is unavailable, say the semantic modality was **unreached** and
fall back to `adr explain` on whatever paths are known, plus lexical search over
the corpus. Report the fallback as the narrower instrument it is: it answers
"what governs this path", not "what have we decided about this topic", and the
absence of a semantic hit is not evidence that no decision exists.

Keep this read-only apart from writing the index itself. Never edit a record to
improve its retrievability — that rewrites governance to suit a tool.
