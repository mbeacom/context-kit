# Verification Checklist

Use this checklist before trusting a claim set.

1. Gather the claim source: AI answer, plan, PR description, commit message,
   migration note, docs, or handoff.
2. List atomic claims. Split conjunctions, vague wording, and bundled outcomes.
3. For each claim, choose the cheapest evidence source likely to settle it:
   code, config, tests, schemas, migrations, generated files, or docs.
4. Run read-only searches with `Glob` and `Grep`; keep the scope narrow before
   reading full files.
5. Read the primary evidence directly with `Read`.
6. Assign a verdict: confirmed, dubious, refuted, or unable-to-check.
7. Cite `file:line` evidence for confirmed and refuted verdicts.
8. Summarize verdict counts and the highest-risk dubious or refuted items.
9. Flag anything needing executable verification, such as tests, builds,
   migrations, browser checks, or production access, as a follow-up for the
   caller to run.

The verifier is intentionally read-only. It should not run the follow-up command
it recommends.
