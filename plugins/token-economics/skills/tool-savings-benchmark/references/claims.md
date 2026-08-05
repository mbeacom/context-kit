# Claims

How to turn a measurement into a sentence that survives someone checking it.

## Anatomy of a defensible claim

A quotable savings claim names five things. Drop any one and the claim overstates
what was shown:

1. **The command pair** — baseline and candidate, exactly as run.
2. **The corpus** — which repository, at what size or revision.
3. **The magnitude** — token delta and percentage.
4. **The counting grade** — `estimated`, or the tokenizer used.
5. **The preserved answer** — the assertion both arms satisfied.

> On this repository, replacing `rg -n 'func handleAuth' .` with
> `rtk rg -n 'func handleAuth' .` reduced output from 4,210 to 980 estimated
> tokens (−76.7%), with both arms still reporting the `handleAuth` definition.
> Controlled A/B, three runs, heuristic counting.

Compare with the version to avoid: *"rtk cuts tokens by 77%."* Same measurement,
but it has silently generalized across every command, corpus, and workload.

## Scope

A benchmark result is causal for **that command pair on that corpus**. It does
not establish anything about:

- other commands, even similar ones;
- other repositories, or the same one at different size;
- end-to-end session cost, which depends on turn count and cache behavior;
- money, unless tokens are metered and priced.

Widening scope requires more measurements, not stronger wording.

## From tokens to cost

The conversion is where honest measurements usually become dishonest claims.

- **Token class matters.** Saved tool output is input-side. If it would have been
  cached, the recurring portion bills at roughly a tenth of the input rate.
  Pricing it at the input rate overstates the saving several-fold.
- **The saving does recur.** Removing output shrinks the prompt for the rest of
  the session, so it is not purely one-shot. That is a real effect and worth
  stating — at the cache-read rate, not the input rate.
- **Subscriptions do not meter.** On a fixed plan the marginal token costs
  nothing. The benefit is capacity: more work inside the context window and the
  request quota. Say that instead of inventing money.

If a currency figure is genuinely needed, state the price assumption inline so a
reader can challenge it.

## Anti-patterns

| Claim | Problem |
| --- | --- |
| "80% fewer tokens" | No baseline, corpus, or preserved answer. |
| "Saved $400 last month" | Telemetry is observational; no attribution. |
| "Cuts context by 95%" | Almost certainly measured on JSON, quoted for code. |
| "Saves 2M tokens/year" | Projection from one measurement times assumed volume. |
| "Same answers" | Vendor's assertion, not yours. Verify your task's answer. |
| "Reduced spend by 30%" | Compares periods where the work also changed. |

## Negative and null results

`costs` and `inconclusive` are results worth recording. A wrapper that loses on
your corpus has saved you an install, and an inconclusive run tells you the
question is not where your spend is.

Publishing only wins produces a catalog where every tool appears to help, which
is how unmeasured percentages spread in the first place.

## Handing the claim on

A savings figure that will be quoted to someone else is a claim about the world,
so route it through `verify-before-trust` for a verdict with evidence. Give the
verifier the command pair, the corpus, the assertion, and the raw JSON from
`--format json` — enough to re-run it, which is the point.
