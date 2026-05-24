# semgrep

Pattern-based static analysis with a large catalog of community rules, taint
tracking, and CI-friendly output. Heavier and slower than `rg`/`sg` — reach for
it when you want curated rule *packs*, data-flow (taint) analysis, or a CI gate.

## Single ad-hoc pattern

```bash
semgrep -e 'requests.get(...)' --lang python .       # every requests.get call
semgrep -e 'logger.debug($X)' --lang js .            # ellipsis = any args
```

`...` is semgrep's variadic ellipsis; `$X` is a metavariable.

## Registry and rule packs

```bash
semgrep --config=auto .                  # auto-select rules for the repo
semgrep --config p/owasp-top-ten .       # a named pack from the registry
semgrep --config p/python .              # language pack
semgrep --config ./rules/ .              # your own local rule directory
```

## Taint mode (data-flow) rule

Track values from a *source* to a *sink*. Example uses benign names — a value
read from a request flows into a logger call:

```yaml
# rules/flow.yml
rules:
  - id: request-value-into-log
    mode: taint
    languages: [python]
    message: Request-derived value reaches a log sink unsanitized.
    severity: WARNING
    pattern-sources:
      - pattern: request.args.get(...)
    pattern-sanitizers:
      - pattern: sanitize(...)
    pattern-sinks:
      - pattern: logger.info(...)
```

```bash
semgrep --config rules/flow.yml .
```

## When semgrep beats `sg`

- You want a maintained **catalog** of rules (OWASP, framework-specific, secrets).
- You need **taint / data-flow** analysis (source → sanitizer → sink), which
  pure AST matching can't express.
- You want a **CI gate** with severities, baselines, and standard report formats.

Use `sg` instead for quick interactive structural search/rewrite where startup
cost matters.

## Machine-readable output

```bash
semgrep --config=auto --sarif -o results.sarif .     # SARIF for code scanning
semgrep --config=auto --json . | jq '.results | length'
```

Note: semgrep loads grammars and rule sets on startup, so it is noticeably
slower than `sg`/`rg` on small queries — prefer it for batch scans, not REPL-speed
lookups.
