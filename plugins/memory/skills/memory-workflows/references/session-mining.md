# Session Mining

`propose-from-session` extracts the human-visible conversation from GitHub
Copilot CLI session logs and writes **reviewable candidates**. It never creates
memory records and nothing it produces can enter active recall on its own.

```bash
MEMORY="$CONTEXT_KIT_MEMORY_ROOT/scripts/memory-provider.py"

python3 "$MEMORY" propose-from-session ~/.copilot/session-state          # dry run
python3 "$MEMORY" propose-from-session ~/.copilot/session-state --write
python3 "$MEMORY" propose-from-session ~/.copilot/session-state/<id> --write --redact
```

## Why candidates, not records

A transcript is not an atomic memory. The `memory-v1` contract requires a
concise canonical abstraction bound to durable evidence, and the validator
rejects placeholder text — so a mechanical transcript-to-record conversion is
not possible and would not be honest if it were.

Mining therefore stops at extraction with provenance. Authoring a record stays
an explicit judgment step:

1. Run a dry run and read the counts.
2. `--write` the candidates you want to review.
3. Read a candidate and decide what, if anything, is worth retaining.
4. Author a `memory-v1` record whose `source` is the **session log** and whose
   `source_hash` matches the candidate's, marked `review: proposed`.
5. Promote with `record-state <id> --review accepted --reason ...` only after
   checking the evidence.

This preserves the standing rule against silently harvesting transcripts while
still making past sessions usable.

## Attribution is the hard part

Copilot records every session activity in one event stream, so the risk is not
missing content — it is **misattributing it**. A subagent task prompt is written
by the orchestrating model, not by the person. Storing it as a user turn creates
a durable record of words the human never said.

Measured across a real 115-session corpus (729 `user.message` and 28,433
`assistant.message` events):

| `user.message` | Count |
| --- | --- |
| carried `parentAgentTaskId` (subagent task prompts) | 611 |
| carried a `source` (generated skill/agent/command/system context) | 94 |
| **human-authored** | **24** |

All 42 distinct `source` values observed were generated context, so the
*presence* of the field is the reliable signal — not any single prefix. A filter
that drops only `skill-` prefixed sources keeps 657 of those 729 as user turns:
a ~27× over-import of content the person never wrote.

## Extraction rules

Recognition requires a `session.start` event with a non-empty string
`sessionId`. A recognized session with no conversational turns is recorded as
empty rather than falling back to raw event JSON.

| Event | Kept when | Dropped when |
| --- | --- | --- |
| `user.message` | no `parentAgentTaskId` **and** no `source` field | subagent task prompt, or generated context |
| `assistant.message` | no `parentToolCallId` **and** no `parentAgentTaskId` | tool-nested or subagent reply |
| everything else | never | always |

Additionally:

- `content` is used, never `transformedContent` — the former is what the person
  typed, the latter is post-expansion.
- `reasoningText` and `reasoningOpaque` are never extracted. Hidden reasoning is
  not capturable under the contract.
- Turns are truncated at 2000 characters with an explicit marker, and a
  candidate holds at most 400 turns.

## Safety

- **Dry run is the default.** `--write` is required to create anything, and the
  dry-run plan reports kept turns and dropped counts by reason.
- **Credential gate.** Extracted text is scanned for high-signal credential
  shapes (AWS key ids, GitHub/Slack tokens, private-key headers, JWTs, and
  assigned `api_key`/`password`/`token` values). A finding **blocks** the write
  and reports the pattern and match count. `--redact` masks the spans as
  `[redacted:<pattern>]` and records a `redactions` count instead.
- **Anchors are required.** The run resolves `repository`, `branch`, and `head`
  from `--repo` and refuses when the repository does not match the configured
  memory project. Anchors are never invented.
- **Project isolation.** Candidates are written to
  `${CONTEXT_KIT_MEMORY_HOME}/candidates/<project-key>/`, keyed by the SHA-256
  of the configured project identifier.
- **Write-once.** Candidate filenames include the source hash, so re-running
  does not silently overwrite a prior extraction.

## Candidate shape

```yaml
schema: context-kit/memory-candidate-v1
session_id: 9d247cbf-…
scope: project
repository: owner/name
branch: main
head: 39bd810…
producer: copilot-agent
observed_at: 2026-08-05T10:00:00.000Z   # from session.start
extracted_at: 2026-08-05T12:57:18+00:00
source: /Users/…/events.jsonl
source_hash: 333ec24a…
turns: 3
redactions: 0
review: candidate
```

The body carries a provenance note, per-reason dropped counts, the transcript,
and review instructions. `review: candidate` is deliberately outside the
`memory-v1` review vocabulary so a candidate can never be mistaken for a
proposed record.
