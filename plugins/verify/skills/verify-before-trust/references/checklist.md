# Verification Checklist

Use this checklist before trusting a claim set.

1. Gather the claim source: AI answer, plan, PR description, commit message,
   migration note, docs, or handoff.
2. List atomic claims. Split conjunctions, vague wording, and bundled outcomes.
3. For each claim, choose the cheapest evidence source likely to settle it:
   code, config, tests, schemas, migrations, generated files, or docs.
4. Run read-only searches by file name and by content; keep the scope narrow
   before reading full files.
5. Read the primary evidence directly.
6. Assign a verdict: confirmed, dubious, refuted, or unable-to-check.
7. Cite `file:line` evidence for confirmed and refuted verdicts settled by static
   inspection. See the evidence forms in `verdicts.md` for the one other accepted
   citation, used when reassessing a claim from a supplied observation report.
8. Summarize verdict counts and the highest-risk dubious or refuted items.
9. Flag anything needing executable verification, such as tests, builds,
   migrations, browser checks, or production access, as a follow-up for the
   caller to run. Name the exact check, not a general suggestion to test more.

The verifier is intentionally read-only. It should not run the follow-up command
it recommends.

For a runtime claim, the follow-up has a defined destination: escalate it with
`/collect-runtime-evidence` when the `runtime-evidence` plugin is installed, then
bring the returned report back and reassess the same claim under this taxonomy.
Leaving the verdict at `unable-to-check` is correct when neither a reviewed
command ID nor an approved, available observation tool can settle the claim.
