# Memory Provider Qualification Policy

This document defines the criteria a candidate memory provider must meet before
it can be used as an optional runtime backend in `context-kit/memory`. Criteria
are not aspirational — each must be demonstrably satisfied at evaluation time.
Where a candidate partially meets a criterion today, the decision table below
records that state and lists concrete, objective revisit triggers.

## Qualification criteria

### 1. Versioned distribution and release policy

The provider must publish versioned releases (tags, GitHub Releases, PyPI, npm,
or equivalent) sufficient for a consuming tool to pin and reproducibly install a
known artifact. Source-only "install from main" does not qualify. A stable
semver surface is preferred; at minimum, a discrete version identifier must
exist per release.

### 2. Stable CLI/MCP/HTTP contract

The provider must document a stable interface — a CLI with a versioned command
surface, an MCP server with a stable capability set, or an HTTP API with versioned
endpoints — that allows `context-kit` to issue exact argv calls or structured
requests without shell interpolation. Breaking changes must be version-gated.
Undocumented or rapidly-changing interfaces do not qualify.

### 3. Project/tenant isolation

Each configured project must write to and read from a namespace that is
structurally isolated from other projects. Writes for project A must not be
retrievable by a recall against project B, including under error conditions.
The isolation mechanism must be documented and testable.

### 4. Provenance and immutable evidence round-tripping

The provider must round-trip all required `context-kit/memory-v1` frontmatter
fields — including `source`, `source_hash`, `repository`, `branch`, `head`,
`observed_at`, and `captured_at` — without truncation, coercion, or silent
transformation. Immutable evidence sections must be preserved verbatim.
Lossy storage disqualifies a provider for use with evidence-bound records.

### 5. Review/freshness/supersession semantics

The provider must either natively preserve `review`, `freshness`, and
`supersedes` state, or pass them through as opaque frontmatter that survives
export. The semantics of proposed → accepted, superseded records, and revoked
records must not be destroyed by the provider's internal representation.

### 6. Explicit credential, network, and privacy behavior

The provider must declare clearly whether it requires credentials, makes
outbound network calls, and under what conditions data is transmitted outside
the local machine. Implicit or undocumented cloud requirements disqualify a
provider for use in offline or privacy-constrained environments. The boundary
between on-device storage and any cloud-backed component must be stated and
must be controllable.

### 7. Export, delete, reindex, and reconciliation

The provider must expose commands or APIs for: exporting all records in a
recoverable format, deleting individual records or an entire project store,
and reindexing from exported records. These are required for migration,
audit compliance, and disaster recovery. Without them, data can become
inaccessible when the provider changes.

### 8. Deterministic errors and timeouts

The provider must return deterministic, inspectable error codes or structured
messages when operations fail, and must respect configurable or documented
timeouts. Silent failures, hung processes, and ambiguous exit codes are
disqualifying because they can corrupt the capture loop.

### 9. Offline or explicitly declared cloud requirements

If the provider requires connectivity at any point in the capture, recall, or
review lifecycle, that requirement must be documented per-operation. Offline-capable
operation — or an explicit, toggleable cloud mode — is required.

### 10. Compatibility tests

The provider must have a test suite exercising the capture/recall/search
round-trip that can be run locally without special access. CI must exist and
must pass on published releases. The test surface must be large enough to
detect regressions in the interface `context-kit` depends on.

### 11. Licensing and maintenance

The provider must carry a license compatible with MIT usage by `context-kit`
consumers. The project must have evidence of active maintenance (commits,
releases, or a stated long-term support policy) sufficient to make the
integration viable over a reasonable horizon.

### 12. Host integration boundaries

The provider must operate without requiring a persistent daemon started by
`context-kit`. It must not assume Claude Code hooks are available, since GitHub
Copilot and APM do not run them. Any host-specific integration (MCP server,
Copilot extension, IDE plugin) must be separately installable and must not be
a prerequisite for CLI-driven capture and recall.

---

## Current provider decision table

| Provider | Status | Qualification summary |
| --- | --- | --- |
| **Local-only records** | ✅ Supported | Python 3 stdlib only. Stores records in `${CONTEXT_KIT_MEMORY_HOME}` with full frontmatter preservation. No external deps, no network, fully offline. All criteria met. |
| **MemPalace** | ✅ Supported (optional) | Versioned CLI releases on PyPI. Stable CLI contract documented. Project/palace isolation enforced by adapter. Evidence round-tripped via local copy before archival. Export and delete available. MIT-compatible license. Criteria met at integration date. |
| **Microsoft Memora** | 🔬 Design-only | Informs context-kit's memory contract; not a runtime provider. See below. |

### Memora: design influence and current status

[Microsoft Memora](https://github.com/microsoft/Memora) introduced the
three-layer model — retained value, primary memory, and cue links — that
informed the `context-kit/memory-v1` three-layer record (evidence, primary
memory, cue anchors). The underlying ideas are described in the Microsoft
Research report on cognitive memory structures. That design is credited and
incorporated into context-kit's provider-neutral contract.

As of the verified date (2026-07-19), Memora does not qualify as a runtime
provider because:

- **Criterion 1 (versioned distribution):** One public initial commit (2026-06-16).
  No tags, no GitHub Releases, no PyPI or package index entry. Only source-only
  installation is documented.
- **Criterion 2 (stable contract):** No documented stable CLI/MCP/HTTP interface.
  The public integration surface is a Python library (`MemoraClient`). Adapting
  to a library-only API introduces an import dependency `context-kit` explicitly
  avoids.
- **Criterion 4 (provenance round-tripping):** No evidence of
  `context-kit/memory-v1` frontmatter preservation. The Memora storage model
  has not been tested against this schema.
- **Criterion 6 (credential/network/privacy):** Setup requires configured Azure
  OpenAI or OpenAI LLM and embedding services. The credential and network scope
  is substantial and cloud-mandatory with no documented offline mode.
- **Criterion 10 (compatibility tests):** No test CI beyond dependency graph
  automation. The test surface is insufficient to detect regressions in a
  potential adapter.

These are gaps at the current state of the project, not permanent assessments.
The decision is time-bounded. Revisit when **all** of the following objective
triggers are satisfied:

1. At least one tagged release or published package version exists.
2. A stable, versioned CLI or MCP interface is documented.
3. An offline or credential-free mode is available, or the cloud requirement
   is fully explicit per-operation with a documented toggle.
4. A test suite covering the capture/recall round-trip can be run locally.
5. A contributor has validated `context-kit/memory-v1` frontmatter
   round-tripping against the published release.

Until those triggers are satisfied, Memora's design remains a credited
influence and its abstraction vocabulary continues to shape the contract.
No provider adapter code targets it.

---

## Policy maintenance

This document records objective state at a point in time. When a revisit
trigger is met, open a tracking issue, run the full qualification checklist
against the candidate release, and update the decision table with the new
state and a dated assessment note. Do not promote a provider to "supported"
without completing all twelve criteria.
