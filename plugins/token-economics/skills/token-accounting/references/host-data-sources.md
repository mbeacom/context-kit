# Host data sources

Exact shapes of the local records this plugin reads. Both formats are internal
to their host and carry **no stability guarantee** — neither is a documented
public interface. Treat a schema change as expected maintenance, and prefer
failing loudly over emitting a number derived from a guess.

## Claude Code transcripts

**Location:** `~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl`, with
subagent transcripts nested under `subagents/`. The directory name is the
absolute working directory with path separators replaced by `-`. Override with
`CONTEXT_KIT_CLAUDE_PROJECTS`.

One JSON object per line. Lines are appended live, so a truncated trailing line
is normal and must be skipped rather than treated as corruption.

Fields observed on assistant lines:

| Field | Meaning |
| --- | --- |
| `type` | `assistant`, `user`, `attachment`, … |
| `requestId` | API request identifier |
| `message.id` | API message identifier |
| `message.model` | model that served the response |
| `message.usage` | token counts (below) |
| `sessionId`, `uuid`, `parentUuid` | session and turn threading |
| `cwd`, `gitBranch`, `version` | environment at the time of the call |
| `isSidechain`, `agentId` | set for subagent traffic |
| `toolUseResult` | tool output payload on `user` lines |

`message.usage` keys:

| Key | Notes |
| --- | --- |
| `input_tokens` | **excludes** cache tokens |
| `output_tokens` | generated tokens |
| `cache_creation_input_tokens` | cache write; premium rate |
| `cache_read_input_tokens` | cache read; heavily discounted |

Total input-side traffic is the sum of all three input fields. Anthropic API
semantics make `input_tokens` the billable uncached figure as written.

### Deduplication is mandatory

The same response appears in several files: a resumed session replays history,
and a subagent transcript repeats the parent's records. Deduplicate on the pair
`(requestId, message.id)`.

Both parts matter. One request may stream more than one message, so keying on
`requestId` alone under-counts. Measured on a live machine with 856 transcripts:
43,615 usage records reduced to 17,265 distinct responses — **60.4% duplicates**,
and a naive sum overstated tokens by **132.6%**.

A record missing both identifiers cannot be deduplicated. Count it and disclose
it; do not drop it silently.

## GitHub Copilot CLI session store

**Location:** `~/.copilot/session-store.db`, SQLite. Override with
`CONTEXT_KIT_COPILOT_DB`. Open read-only (`file:…?mode=ro`) so a live session is
never disturbed.

Relevant table:

```sql
CREATE TABLE assistant_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    turn_index INTEGER,
    agent_id TEXT,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_write_tokens INTEGER,
    reasoning_tokens INTEGER,
    total_nano_aiu INTEGER,
    request_multiplier REAL,
    duration_ms INTEGER,
    initiator TEXT,
    token_details_json TEXT,
    created_at TEXT
);
```

Companion tables include `sessions` (`cwd`, `repository`, `branch`), `turns`,
`session_files`, and `session_refs`.

### `input_tokens` includes cache traffic

This is the opposite of Claude Code and the single most dangerous difference.
A live row:

```text
input_tokens 168187 = input 419 + cache_read 165500 + cache_write 2268
```

Pricing `168187` at the uncached input rate overstates that component by ~400×.
Across a full store the aggregate error was ~950×. Billable uncached input is
`input_tokens − cache_read_tokens − cache_write_tokens`.

Unlike Claude Code, rows are not duplicated — each is one billed request.

### Cost is exact and self-describing

`total_nano_aiu` is the recorded charge in nano-AI-Units (1e-9 AIU).
`token_details_json` carries the per-class rate card actually applied:

```json
[{"batchSize": 1000000, "costPerBatch": 500000000000,
  "tokenCount": 419, "tokenType": "input"}]
```

The identity below held on **400 of 400** sampled rows:

```text
total_nano_aiu == Σ (tokenCount / batchSize) × costPerBatch
```

So cost needs no external price table and cannot go stale. Observed rate ratios
match Anthropic's published structure — cache read `0.1×` input, cache write
`1.25×`, output `5×` (`6×` for one GPT model) — and differ per model.

`request_multiplier` (for example `15.0` for Opus-class models) is **not** folded
into `total_nano_aiu`; the identity holds without it. It accounts for premium
request quota separately. Multiplying the two double-counts.

## What neither source provides

- **Claude Code records no cost.** Tokens are exact; currency is your assumption.
- **No tool-level attribution.** Neither store says which tool call caused which
  tokens, so per-tool savings cannot be derived from telemetry. That requires the
  controlled comparison in `tool-savings-benchmark`.
- **No offline tokenizer for Claude models.** Anthropic's
  `/v1/messages/count_tokens` endpoint is the only exact route; local counting is
  heuristic.
