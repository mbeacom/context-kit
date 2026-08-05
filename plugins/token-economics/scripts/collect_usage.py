#!/usr/bin/env python3
"""Read local agent usage records and report token totals that survive review.

Two hosts write token counts to disk in different shapes, and each shape has a
trap that silently inflates a naive total:

* Claude Code writes one JSONL line per API response under
  ``~/.claude/projects``. Resumed sessions, sidechains, and subagent transcripts
  replay the same response, so the same ``(requestId, message.id)`` pair recurs.
  Its ``input_tokens`` EXCLUDES cache tokens.
* GitHub Copilot CLI writes ``assistant_usage_events`` rows to the SQLite
  database ``~/.copilot/session-store.db``. Its ``input_tokens`` INCLUDES
  ``cache_read_tokens`` and ``cache_write_tokens``, so pricing that column at the
  uncached input rate overstates cost by orders of magnitude.

This script normalizes both into one record shape, deduplicates, and separates
billable-uncached input from cache traffic. It only ever reads.

Cost is reported only where the host records it. Copilot rows carry their own
per-model rate card in ``token_details_json``, so cost is exact and needs no
price table. Claude Code records no cost, so this script reports tokens and
leaves cost to the caller rather than embedding a price list that goes stale.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "context-kit/token-usage-v1"


def _display_path(path: Path) -> str:
    """Abbreviate a source path so a pasted report does not carry a home dir.

    A usage report is written to be shared, and an absolute path names the
    developer and can expose private repository or machine layout. `--raw-paths`
    restores the literal path for local debugging.
    """
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


# Copilot expresses cost in nano-AIU (1e-9 AI Units) so integer arithmetic stays
# exact; convert only for display.
NANO_PER_AIU = 1_000_000_000

CLAUDE_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


class CollectError(RuntimeError):
    """A usage source could not be read in a way the caller must know about."""


@dataclass
class Totals:
    """Token totals with cache traffic separated from billable-uncached input.

    ``input_uncached`` is the only input-side figure that carries the full input
    rate on either host. Keeping it distinct from ``cache_read``/``cache_write``
    is what makes a cost estimate defensible.
    """

    requests: int = 0
    input_uncached: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    reasoning: int = 0
    cost_nano_aiu: int = 0
    cost_recorded: bool = False

    def add(self, other: Totals) -> None:
        self.requests += other.requests
        self.input_uncached += other.input_uncached
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.output += other.output
        self.reasoning += other.reasoning
        self.cost_nano_aiu += other.cost_nano_aiu
        self.cost_recorded = self.cost_recorded or other.cost_recorded

    @property
    def total_tokens(self) -> int:
        return self.input_uncached + self.cache_read + self.cache_write + self.output

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["total_tokens"] = self.total_tokens
        # cache_read is billed at a small fraction of the input rate on both
        # hosts, so a raw token count overstates the value of avoiding it. Report
        # the hit rate rather than implying every token is equally expensive.
        input_side = self.input_uncached + self.cache_read + self.cache_write
        data["cache_hit_ratio"] = (
            round(self.cache_read / input_side, 4) if input_side else None
        )
        if self.cost_recorded:
            data["cost_aiu"] = round(self.cost_nano_aiu / NANO_PER_AIU, 6)
        else:
            data["cost_aiu"] = None
        return data


@dataclass
class Report:
    host: str
    source: str
    counting: str
    attribution: str
    totals: Totals = field(default_factory=Totals)
    by_model: dict[str, Totals] = field(default_factory=dict)
    duplicates_skipped: int = 0
    files_read: int = 0
    notes: list[str] = field(default_factory=list)

    def record(self, model: str, totals: Totals) -> None:
        self.totals.add(totals)
        bucket = self.by_model.setdefault(model, Totals())
        bucket.add(totals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "source": self.source,
            "counting": self.counting,
            "attribution": self.attribution,
            "files_read": self.files_read,
            "duplicates_skipped": self.duplicates_skipped,
            "totals": self.totals.as_dict(),
            "by_model": {k: v.as_dict() for k, v in sorted(self.by_model.items())},
            "notes": self.notes,
        }


def _int(value: Any) -> int:
    """Coerce a possibly-missing or non-numeric token count to a usable int."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def claude_projects_dir(root: Path | None = None) -> Path:
    if root is not None:
        return root
    env = os.environ.get("CONTEXT_KIT_CLAUDE_PROJECTS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude" / "projects"


def copilot_db_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    env = os.environ.get("CONTEXT_KIT_COPILOT_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".copilot" / "session-store.db"


def iter_jsonl_usage(
    path: Path,
) -> Iterator[tuple[str, dict[str, Any], str | None, str | None]]:
    """Yield ``(model, usage, request_id, message_id)`` for assistant responses.

    Malformed lines are skipped rather than aborting: transcripts are appended
    live, so a partially written trailing line is normal.
    """
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(entry, dict):
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            model = message.get("model") or "unknown"
            yield str(model), usage, entry.get("requestId"), message.get("id")


def collect_claude(root: Path | None = None, *, raw_paths: bool = False) -> Report:
    """Total Claude Code transcript usage, deduplicated by API response."""
    projects = claude_projects_dir(root)
    report = Report(
        host="claude-code",
        source=str(projects) if raw_paths else _display_path(projects),
        counting="exact",
        attribution="observational",
    )
    if not projects.is_dir():
        report.notes.append(
            f"no Claude Code transcripts at {report.source}; reported as absent, not as zero usage"
        )
        return report

    seen: set[tuple[str, str]] = set()
    unkeyed = 0
    unrecognized = 0
    unreadable: list[str] = []
    for path in sorted(projects.rglob("*.jsonl")):
        try:
            records = list(iter_jsonl_usage(path))
        except OSError as exc:
            # Transcripts are written live and may be rotated, deleted, or owned
            # by another user. One unreadable file must not discard every record
            # already collected, but it must be disclosed rather than ignored.
            unreadable.append(f"{path.name} ({exc.strerror or exc})")
            continue
        report.files_read += 1
        for model, usage, request_id, message_id in records:
            # A response is uniquely identified by its request and message id.
            # Both are needed: one request can stream more than one message, and
            # the same message is replayed into subagent transcripts.
            if request_id and message_id:
                key = (str(request_id), str(message_id))
                if key in seen:
                    report.duplicates_skipped += 1
                    continue
                seen.add(key)
            else:
                unkeyed += 1
            if not any(k in usage for k in CLAUDE_USAGE_FIELDS):
                # The record has a usage object with none of the token keys this
                # reader knows. Counting it as zero would report a confident
                # `exact` total after a host format change; surface it instead.
                unrecognized += 1
            totals = Totals(
                requests=1,
                # Claude Code follows Anthropic API semantics: input_tokens is
                # already exclusive of both cache fields, so it is the billable
                # uncached figure as written.
                input_uncached=_int(usage.get("input_tokens")),
                cache_read=_int(usage.get("cache_read_input_tokens")),
                cache_write=_int(usage.get("cache_creation_input_tokens")),
                output=_int(usage.get("output_tokens")),
            )
            report.record(model, totals)

    if unreadable:
        shown = ", ".join(unreadable[:5])
        if len(unreadable) > 5:
            shown += f", and {len(unreadable) - 5} more"
        report.notes.append(
            f"{len(unreadable)} transcript(s) could not be read and are missing from "
            f"these totals: {shown}"
        )
    if unrecognized:
        report.notes.append(
            f"{unrecognized} record(s) carried a usage object with none of the "
            f"expected token fields {list(CLAUDE_USAGE_FIELDS)}; this host's format "
            "may have changed and those records contributed nothing"
        )
        if unrecognized == report.totals.requests:
            # Every record was unreadable, so the total is not a measurement.
            report.counting = "unknown"
    if unkeyed:
        report.notes.append(
            f"{unkeyed} record(s) lacked requestId and message.id and could not be "
            "deduplicated; totals may double-count those responses"
        )
    report.notes.append(
        "input_uncached comes from input_tokens, which Anthropic reports exclusive "
        "of cache tokens"
    )
    report.notes.append(
        "Claude Code records no cost; tokens are exact but any USD figure is the "
        "caller's own price assumption"
    )
    return report


def _copilot_uncached_input(
    input_tokens: int, cache_read: int, cache_write: int, details: Any
) -> tuple[int, bool]:
    """Return billable-uncached input for a Copilot row and whether it was exact.

    ``token_details_json`` carries the authoritative per-class split. When it is
    present the uncached figure is read directly; otherwise it is derived by
    subtracting cache traffic from the inclusive ``input_tokens`` column, which
    is exact arithmetic but relies on the documented column semantics.
    """
    if isinstance(details, str) and details:
        try:
            parsed = json.loads(details)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and item.get("tokenType") == "input":
                    return _int(item.get("tokenCount")), True
    derived = input_tokens - cache_read - cache_write
    return (max(0, derived)), False


def collect_copilot(db: Path | None = None, *, raw_paths: bool = False) -> Report:
    """Total GitHub Copilot CLI usage from the local session store."""
    path = copilot_db_path(db)
    report = Report(
        host="github-copilot-cli",
        source=str(path) if raw_paths else _display_path(path),
        counting="exact",
        attribution="observational",
    )
    if not path.is_file():
        report.notes.append(
            f"no Copilot session store at {report.source}; reported as absent, not as zero usage"
        )
        return report

    # Percent-encode the path before building the URI: `#` and `?` are legal in
    # POSIX filenames, and an unescaped one truncates the query string, silently
    # dropping mode=ro and reopening read-write-create.
    uri = f"file:{urllib.parse.quote(str(path))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - environment dependent
        raise CollectError(f"cannot open {path} read-only: {exc}") from exc

    derived_rows = 0
    uncosted = 0
    try:
        conn.row_factory = sqlite3.Row
        try:
            # sqlite3 fetches lazily, so a corrupt page or a lock surfaces during
            # iteration rather than at execute(). Both must land here, otherwise
            # a damaged store escapes as a traceback and exits 1 — the code that
            # means "no records found".
            rows = conn.execute(
                "SELECT model, input_tokens, output_tokens, cache_read_tokens, "
                "cache_write_tokens, reasoning_tokens, total_nano_aiu, "
                "token_details_json FROM assistant_usage_events"
            )
            report.files_read = 1
            for row in rows:
                cache_read = _int(row["cache_read_tokens"])
                cache_write = _int(row["cache_write_tokens"])
                uncached, exact = _copilot_uncached_input(
                    _int(row["input_tokens"]),
                    cache_read,
                    cache_write,
                    row["token_details_json"],
                )
                if not exact:
                    derived_rows += 1
                if row["total_nano_aiu"] is None:
                    uncosted += 1
                totals = Totals(
                    requests=1,
                    input_uncached=uncached,
                    cache_read=cache_read,
                    cache_write=cache_write,
                    output=_int(row["output_tokens"]),
                    reasoning=_int(row["reasoning_tokens"]),
                    cost_nano_aiu=_int(row["total_nano_aiu"]),
                    # The column is nullable. Treating NULL as recorded would
                    # present 0 AIU as an exact host charge, which is the kind
                    # of confident-but-wrong figure this reader exists to avoid.
                    cost_recorded=row["total_nano_aiu"] is not None,
                )
                report.record(str(row["model"] or "unknown"), totals)
        except sqlite3.Error as exc:
            raise CollectError(f"cannot read usage rows from {path}: {exc}") from exc
    finally:
        conn.close()

    report.notes.append(
        "input_tokens on this host INCLUDES cache traffic; input_uncached is the "
        "billable remainder, so do not price the raw column"
    )
    if derived_rows:
        report.notes.append(
            f"{derived_rows} row(s) had no token_details_json; uncached input was "
            "derived by subtracting cache traffic"
        )
    if report.totals.cost_recorded:
        report.notes.append(
            "cost_aiu is the host's own recorded charge in AI Units, not a price "
            "estimate; it excludes premium-request multipliers, which bill separately"
        )
    if uncosted:
        report.notes.append(
            f"{uncosted} row(s) recorded no cost; those requests contribute tokens "
            "but nothing to cost_aiu, so the charge shown is a partial total"
        )
    return report


def build_reports(hosts: Iterable[str], *, raw_paths: bool = False) -> list[Report]:
    reports: list[Report] = []
    for host in hosts:
        if host == "claude":
            reports.append(collect_claude(raw_paths=raw_paths))
        elif host == "copilot":
            reports.append(collect_copilot(raw_paths=raw_paths))
        else:  # pragma: no cover - argparse constrains choices
            raise CollectError(f"unknown host: {host}")
    return reports


def _fmt(value: int) -> str:
    return f"{value:,}"


def render_text(reports: list[Report]) -> str:
    lines: list[str] = []
    for report in reports:
        totals = report.totals
        lines.append(f"# {report.host}")
        lines.append(f"source: {report.source}")
        lines.append(f"counting: {report.counting} | attribution: {report.attribution}")
        if totals.requests == 0:
            lines.append("no usage records found")
            for note in report.notes:
                lines.append(f"note: {note}")
            lines.append("")
            continue
        lines.append(f"requests: {_fmt(totals.requests)}")
        if report.duplicates_skipped:
            lines.append(
                f"duplicates skipped: {_fmt(report.duplicates_skipped)} "
                f"(counting them would have inflated the total)"
            )
        lines.append(f"input (uncached): {_fmt(totals.input_uncached)}")
        lines.append(f"cache read:       {_fmt(totals.cache_read)}")
        lines.append(f"cache write:      {_fmt(totals.cache_write)}")
        lines.append(f"output:           {_fmt(totals.output)}")
        if totals.reasoning:
            lines.append(f"reasoning:        {_fmt(totals.reasoning)}")
        lines.append(f"total tokens:     {_fmt(totals.total_tokens)}")
        ratio = totals.as_dict()["cache_hit_ratio"]
        if ratio is not None:
            lines.append(f"cache hit ratio:  {ratio:.1%} of input-side tokens")
        if totals.cost_recorded:
            lines.append(
                f"recorded cost:    {totals.cost_nano_aiu / NANO_PER_AIU:,.3f} AIU"
            )
        else:
            lines.append("recorded cost:    not recorded by this host")
        if report.by_model:
            lines.append("by model:")
            for model, bucket in sorted(
                report.by_model.items(), key=lambda kv: -kv[1].total_tokens
            ):
                lines.append(
                    f"  {model:<24} {_fmt(bucket.total_tokens):>16} tokens "
                    f"({_fmt(bucket.requests)} req)"
                )
        for note in report.notes:
            lines.append(f"note: {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report local agent token usage with per-host correctness rules."
    )
    parser.add_argument(
        "--host",
        action="append",
        choices=("claude", "copilot"),
        help="host to read; repeatable. Defaults to every supported host.",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="output format"
    )
    parser.add_argument(
        "--raw-paths",
        action="store_true",
        help="print absolute source paths instead of home-relative ones; a report "
        "you intend to share should keep the default",
    )
    args = parser.parse_args(argv)

    hosts = args.host or ["claude", "copilot"]
    try:
        reports = build_reports(hosts, raw_paths=args.raw_paths)
    except CollectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = {
            "schema": SCHEMA,
            "reports": [r.as_dict() for r in reports],
        }
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(render_text(reports), end="")

    # A run that found no records anywhere is not a success; the caller asked
    # about usage and got no evidence either way.
    if all(r.totals.requests == 0 for r in reports):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
