#!/usr/bin/env python3
"""Merge shard findings into a coverage ledger that cannot overstate itself."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

COVERAGE_SCHEMA = "context-kit/corpus-coverage-v1"
FINDINGS_SCHEMA = "context-kit/corpus-findings-v1"
INVENTORY_SCHEMA = "context-kit/corpus-inventory-v1"
SHARDS_SCHEMA = "context-kit/corpus-shards-v1"

REVIEWED = "reviewed"
PARTIAL = "partial"
UNINSPECTABLE = "uninspectable"
OUT_OF_SCOPE = "out_of_scope"
FAILED = "failed"
PENDING = "pending"
DISPOSITIONS = (REVIEWED, PARTIAL, UNINSPECTABLE, OUT_OF_SCOPE, FAILED, PENDING)

FINDING_RE = re.compile(
    r"^-\s*\[(?P<tags>[^\]]+)\]\s*"
    r"\[significance:\s*(?P<significance>[^\]]+)\]\s*"
    r"`(?P<citation>[^`]+)`",
    re.IGNORECASE,
)
CANDIDATE_RE = re.compile(r"^-\s*\[")
HEADING_RE = re.compile(r"^##+\s+(?P<title>.+?)\s*$")

# The four sections the `corpus-reviewer` output contract requires. A report
# missing any of them is truncated, not merely terse.
REQUIRED_SECTIONS = frozenset({"summary", "findings", "gaps observed", "coverage"})


def load_json_file(path: Path, schema: str) -> dict[str, Any]:
    data = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    if data.get("schema") != schema:
        raise ValueError(f"{path.name} schema must be `{schema}`")
    return data


def inventory_digest(inventory: dict[str, Any]) -> str:
    """Hash the inventory's content rather than its file bytes.

    Must stay byte-for-byte equivalent to `plan-shards.py`'s function of the
    same name: the plan's `inventory_sha256` is what proves both scripts are
    working from the same denominator.
    """
    payload = {"scope": inventory.get("scope"), "units": inventory.get("units")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def resolve_output(destination: Path, inventory: dict[str, Any]) -> Path:
    """Refuse to write derived artifacts inside the corpus root.

    An artifact written into the corpus is enumerated by the next inventory
    run, which inflates the denominator with the review's own output.
    """
    resolved = destination.expanduser().resolve()
    raw_root = inventory.get("root")
    if not isinstance(raw_root, str) or not raw_root:
        return resolved
    root = Path(raw_root).expanduser().resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(
            f"refusing to write inside the corpus root ({root}); use a separate "
            "work directory so a re-run does not enumerate its own artifacts"
        )
    return resolved


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse a minimal frontmatter block whose values are JSON or bare scalars.

    Deliberately not a YAML parser: the findings header is a fixed, small shape,
    and depending on a YAML library would put a third-party requirement in the
    middle of a standard-library-only pipeline.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    fields: dict[str, Any] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, "\n".join(lines[index + 1 :])
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = _coerce(value.strip())
    return None, text


def _coerce(value: str) -> Any:
    if value[:1] in {"[", "{", '"'}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def split_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    sections[current] = []
    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            current = match.group("title").strip().lower()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def parse_findings_section(lines: Sequence[str]) -> tuple[list[dict[str, str]], int]:
    """Return parsed findings and the count of bullets that failed to parse.

    Each finding keeps its indented continuation block — the Observation,
    Evidence, and Why-it-matters lines the worker contract requires. Storing
    only the marker line would reduce every finding to a tag and a citation,
    leaving the aggregate outputs with no substance to act on.

    An unparsed bullet is counted rather than dropped: a reviewer who wrote the
    marker slightly differently should see a warning, not lose the finding.
    """
    findings: list[dict[str, str]] = []
    unparsed = 0
    current: dict[str, str] | None = None
    body: list[str] = []

    def flush() -> None:
        if current is not None:
            current["body"] = "\n".join(body).strip()
            findings.append(current)

    for line in lines:
        stripped = line.strip()
        if CANDIDATE_RE.match(stripped):
            flush()
            current, body = None, []
            match = FINDING_RE.match(stripped)
            if match is None:
                unparsed += 1
                continue
            tags = [tag.strip().upper() for tag in match.group("tags").split(",")]
            current = {
                "tags": ",".join(tag for tag in tags if tag),
                "significance": match.group("significance").strip().lower(),
                "citation": match.group("citation").strip(),
                "text": stripped,
            }
            continue
        if current is not None and line.startswith((" ", "\t")) and stripped:
            body.append(stripped)
            continue
        if not stripped:
            continue
        flush()
        current, body = None, []
    flush()
    return findings, unparsed


def _id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _reason_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            out.append(
                {
                    "id": item["id"],
                    "reason": str(item.get("reason", "unspecified")),
                }
            )
    return out


class Ledger:
    """Assign exactly one disposition to every inventory unit."""

    def __init__(self, inventory: dict[str, Any]) -> None:
        self.units: dict[str, dict[str, Any]] = {
            unit["id"]: unit for unit in inventory["units"]
        }
        self.disposition: dict[str, str] = {}
        self.reasons: dict[str, str] = {}
        for unit_id, unit in self.units.items():
            self.disposition[unit_id] = (
                PENDING if unit.get("in_scope") else OUT_OF_SCOPE
            )

    def assign(self, unit_id: str, disposition: str, reason: str | None = None) -> None:
        self.disposition[unit_id] = disposition
        if reason:
            self.reasons[unit_id] = reason

    def counts(self) -> dict[str, int]:
        counts = {name: 0 for name in DISPOSITIONS}
        for value in self.disposition.values():
            counts[value] = counts.get(value, 0) + 1
        return counts

    def entries(self) -> list[dict[str, Any]]:
        """Return every unit with its disposition, in inventory order."""
        return [
            {
                "id": unit_id,
                "path": self.units[unit_id]["path"],
                "bytes": self.units[unit_id]["bytes"],
                "range": self.units[unit_id].get("range"),
                "disposition": self.disposition[unit_id],
                "reason": self.reasons.get(unit_id),
            }
            for unit_id in sorted(self.disposition)
        ]

    def bytes_for(self, disposition: str) -> int:
        return sum(
            int(self.units[unit_id]["bytes"])
            for unit_id, value in self.disposition.items()
            if value == disposition
        )

    def in_scope_bytes(self) -> int:
        return sum(
            int(unit["bytes"]) for unit in self.units.values() if unit.get("in_scope")
        )


def read_shard_report(
    shard: dict[str, Any], findings_dir: Path
) -> tuple[str, dict[str, Any], list[dict[str, str]], int, str]:
    """Classify one shard's findings file.

    Returns (status, frontmatter, findings, unparsed_count, findings_text).
    The last element is the text of the Findings section only — see `_absence`
    for why the rest of the report must not count as evidence of presence.
    """
    path = findings_dir / f"{shard['id']}.md"
    if not path.is_file():
        return PENDING, {}, [], 0, ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return FAILED, {}, [], 0, ""
    except UnicodeDecodeError:
        # A report we cannot decode is unusable, not fatal. Failing the shard
        # keeps the ledger computable so the rest of the run is still reportable.
        return FAILED, {}, [], 0, ""

    fields, body = parse_frontmatter(text)
    if fields is None:
        return FAILED, {}, [], 0, ""
    if fields.get("schema") != FINDINGS_SCHEMA:
        return FAILED, fields, [], 0, ""
    if str(fields.get("shard", "")).strip('"') != shard["id"]:
        return FAILED, fields, [], 0, ""
    if str(fields.get("digest", "")).strip('"') != shard["digest"]:
        return "stale_digest", fields, [], 0, ""

    sections = split_sections(body)
    # A header alone is not a report. Without this check a truncated file whose
    # frontmatter claims every unit was reviewed would count as full coverage
    # while carrying no findings, gaps, or coverage statement at all.
    if not REQUIRED_SECTIONS <= set(sections):
        return FAILED, fields, [], 0, ""

    findings_lines = sections.get("findings", [])
    findings, unparsed = parse_findings_section(findings_lines)
    return "complete", fields, findings, unparsed, "\n".join(findings_lines)


def aggregate(
    inventory: dict[str, Any],
    inventory_sha256: str,
    shards: dict[str, Any],
    findings_dir: Path,
    expected: Sequence[str] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    if shards.get("inventory_sha256") != inventory_sha256:
        raise ValueError(
            "shard plan was built from a different inventory; re-plan shards "
            "before aggregating, or coverage would be computed against the "
            "wrong denominator"
        )

    inventory_errors = inventory.get("errors")
    inventory_errors = inventory_errors if isinstance(inventory_errors, list) else []
    if inventory_errors:
        warnings.append(
            f"{len(inventory_errors)} directory/directories could not be traversed "
            "at inventory time; their files are missing from this denominator, so "
            "coverage is measured against a known-incomplete corpus"
        )

    ledger = Ledger(inventory)
    shard_status: dict[str, int] = {
        "complete": 0,
        "failed": 0,
        "pending": 0,
        "stale_digest": 0,
    }
    all_findings: list[dict[str, Any]] = []
    findings_prose: list[str] = []
    # Shards a re-run must handle: failed, stale, pending, and any shard whose
    # worker left units unaccounted for.
    redispatch: set[str] = set()

    for shard in shards["shards"]:
        member_ids = {unit["id"] for unit in shard["units"]}
        status, fields, findings, unparsed, findings_text = read_shard_report(
            shard, findings_dir
        )
        shard_status[status] = shard_status.get(status, 0) + 1

        if status == FAILED:
            for unit_id in sorted(member_ids):
                ledger.assign(unit_id, FAILED, "shard findings file is unusable")
            warnings.append(
                f"shard {shard['id']}: findings file is unusable — it is not "
                "decodable, lacks valid frontmatter, or is missing a required "
                "section from the reviewer output contract"
            )
            redispatch.add(shard["id"])
            continue
        if status == "stale_digest":
            warnings.append(
                f"shard {shard['id']}: findings digest does not match the plan; "
                "the corpus changed under the review"
            )
            redispatch.add(shard["id"])
            continue
        if status == PENDING:
            redispatch.add(shard["id"])
            continue

        findings_prose.append(findings_text)
        if unparsed:
            warnings.append(
                f"shard {shard['id']}: {unparsed} finding bullet(s) did not match "
                "the expected marker and were not counted"
            )

        claimed: set[str] = set()
        buckets = (
            (
                REVIEWED,
                [{"id": item} for item in _id_list(fields.get("units_reviewed"))],
            ),
            (PARTIAL, _reason_list(fields.get("units_partial"))),
            (UNINSPECTABLE, _reason_list(fields.get("units_uninspectable"))),
        )
        for disposition, entries in buckets:
            for entry in entries:
                unit_id = entry["id"]
                if unit_id not in member_ids:
                    warnings.append(
                        f"shard {shard['id']}: claims unit `{unit_id}` that is not "
                        "in its assignment"
                    )
                    continue
                if unit_id in claimed:
                    ledger.assign(unit_id, FAILED, "claimed in multiple buckets")
                    warnings.append(
                        f"shard {shard['id']}: unit `{unit_id}` claimed more than once"
                    )
                    continue
                claimed.add(unit_id)
                ledger.assign(unit_id, disposition, entry.get("reason"))

        for unit_id in sorted(member_ids - claimed):
            warnings.append(
                f"shard {shard['id']}: unit `{unit_id}` was never accounted for"
            )
            redispatch.add(shard["id"])

        for finding in findings:
            all_findings.append({"shard": shard["id"], **finding})

    counts = ledger.counts()
    in_scope_units = counts[REVIEWED] + counts[PARTIAL]
    in_scope_units += counts[UNINSPECTABLE] + counts[FAILED] + counts[PENDING]
    in_scope_bytes = ledger.in_scope_bytes()
    coverage = {
        "units": _ratio(counts[REVIEWED], in_scope_units),
        "bytes": _ratio(ledger.bytes_for(REVIEWED), in_scope_bytes),
    }
    if in_scope_units == 0:
        warnings.append(
            "no in-scope units: the scope rules matched nothing, so this run "
            "read no material; check --include and --exclude before treating "
            "any result as coverage"
        )

    # `complete` answers "is there work left to re-dispatch?" — `pending`,
    # `failed`, and `stale_digest` are retryable, while `partial` and
    # `uninspectable` are recorded limitations a re-run cannot fix. A run with
    # no in-scope units is not a finished review either: it read nothing, so it
    # must not present as complete.
    blocking = counts[PENDING] + counts[FAILED] + shard_status["stale_digest"]
    complete = blocking == 0 and in_scope_units > 0

    generated = (now or datetime.now(timezone.utc)).isoformat()
    # The per-unit map is the ledger's actual product. Counts alone let a reader
    # see that eight units are pending without being able to name them, which
    # makes the plugin's central claim — every unit is accounted for — unprovable
    # and leaves no way to target a re-dispatch.
    unit_ledger = ledger.entries()
    ledger_doc = {
        "schema": COVERAGE_SCHEMA,
        "generated_at": generated,
        "inventory_sha256": inventory_sha256,
        "complete": complete,
        "dispositions": counts,
        "coverage": coverage,
        "shards": {"total": len(shards["shards"]), **shard_status},
        "inventory_errors": inventory_errors,
        "units": unit_ledger,
        "uninspectable": [
            entry for entry in unit_ledger if entry["disposition"] == UNINSPECTABLE
        ],
        "needs_attention": {
            name: [entry for entry in unit_ledger if entry["disposition"] == name]
            for name in (PENDING, FAILED, PARTIAL)
        },
        "shards_to_redispatch": sorted(redispatch),
        "absence": _absence(
            expected,
            findings_prose,
            counts,
            shard_status,
            in_scope_units,
            bool(inventory_errors),
        ),
        "warnings": warnings,
    }

    # The findings index must be self-describing: it is read on its own, so it
    # carries the coverage ratios and warnings rather than assuming anyone
    # opened the ledger beside it.
    findings_doc = {
        "schema": "context-kit/corpus-findings-index-v1",
        "generated_at": generated,
        "inventory_sha256": inventory_sha256,
        "complete": complete,
        "coverage": coverage,
        "warnings": warnings,
        "totals": {
            "findings": len(all_findings),
            "by_tag": _by_key(all_findings, "tags"),
            "by_significance": _by_key(all_findings, "significance"),
        },
        "findings": all_findings,
    }
    return ledger_doc, findings_doc, warnings


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _by_key(findings: Sequence[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        for value in str(finding.get(key, "")).split(","):
            value = value.strip()
            if value:
                counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _absence(
    expected: Sequence[str] | None,
    findings_prose: Sequence[str],
    counts: dict[str, int],
    shard_status: dict[str, int],
    in_scope_units: int,
    inventory_incomplete: bool = False,
) -> dict[str, Any]:
    """Classify each expected-but-unmentioned item.

    `indeterminate` outranks `not-found`: while any unit is uninspectable,
    partially read, failed, pending, or stale — or the inventory itself could
    not enumerate the whole corpus — absence is not decidable and must not be
    reported as a gap. A partially read unit blocks a `not-found` for the same
    reason an uninspectable one does: its unread portion could hold the item.

    Presence is judged from the Findings sections only. Scanning whole reports
    would let "incident report is absent" in a Gaps section read as proof that
    an incident report was found, silently deleting a real gap from the output.
    """
    if not expected:
        return {
            "available": False,
            "reason": "no expected inventory supplied",
            "not_found": [],
            "indeterminate": [],
        }
    if in_scope_units == 0:
        return {
            "available": False,
            "reason": "no in-scope units were inspected",
            "not_found": [],
            "indeterminate": [],
        }

    blockers = {
        UNINSPECTABLE: counts[UNINSPECTABLE],
        PARTIAL: counts[PARTIAL],
        FAILED: counts[FAILED],
        PENDING: counts[PENDING],
        "stale_digest": shard_status["stale_digest"],
    }
    blocking = {name: value for name, value in blockers.items() if value}
    if inventory_incomplete:
        blocking["untraversable directories"] = 1
    haystack = "\n".join(findings_prose).casefold()

    not_found: list[str] = []
    indeterminate: list[dict[str, str]] = []
    for item in expected:
        if item.casefold() in haystack:
            continue
        if blocking:
            reason = ", ".join(
                f"{value} {name}" for name, value in sorted(blocking.items())
            )
            indeterminate.append(
                {"item": item, "reason": f"absence not decidable: {reason}"}
            )
        else:
            not_found.append(item)
    return {
        "available": True,
        "not_found": not_found,
        "indeterminate": indeterminate,
    }


def render_coverage_markdown(ledger: dict[str, Any]) -> str:
    counts = ledger["dispositions"]
    coverage = ledger["coverage"]
    lines = [
        "# Coverage Ledger",
        "",
        f"- Complete: **{'yes' if ledger['complete'] else 'no'}**",
        f"- Unit coverage: {coverage['units'] * 100:.1f}%",
        f"- Byte coverage: {coverage['bytes'] * 100:.1f}%",
        "",
        "## Dispositions",
        "",
        "| Disposition | Units |",
        "| --- | --- |",
    ]
    lines += [f"| `{name}` | {counts[name]} |" for name in DISPOSITIONS]
    shards = ledger["shards"]
    lines += [
        "",
        "## Shards",
        "",
        f"- total: {shards['total']}",
        f"- complete: {shards['complete']}",
        f"- pending: {shards['pending']}",
        f"- failed: {shards['failed']}",
        f"- stale digest: {shards['stale_digest']}",
        "",
        "## Uninspectable units",
        "",
    ]
    if ledger["uninspectable"]:
        lines += [
            f"- `{entry['path']}` — {entry['reason'] or 'unspecified'}"
            for entry in ledger["uninspectable"]
        ]
    else:
        lines.append("None.")

    lines += ["", "## Units needing attention", ""]
    attention = ledger["needs_attention"]
    if any(attention.values()):
        for name in (PENDING, FAILED, PARTIAL):
            entries = attention[name]
            if not entries:
                continue
            lines += [f"`{name}` ({len(entries)}):", ""]
            lines += [
                f"- `{entry['path']}`"
                + (f" — {entry['reason']}" if entry["reason"] else "")
                for entry in entries
            ]
            lines.append("")
        if ledger["shards_to_redispatch"]:
            joined = ", ".join(f"`{name}`" for name in ledger["shards_to_redispatch"])
            lines += [f"Re-dispatch: {joined}", ""]
        lines.pop()
    else:
        lines.append("None.")

    if ledger["inventory_errors"]:
        lines += ["", "## Untraversable directories", ""]
        lines += [
            f"- `{entry['path']}` — {entry['error']}"
            for entry in ledger["inventory_errors"]
        ]
        lines += [
            "",
            "Their files never entered the denominator, so coverage below is "
            "measured against a known-incomplete corpus.",
        ]

    absence = ledger["absence"]
    lines += ["", "## Absence verdicts", ""]
    if not absence["available"]:
        lines.append(f"Unavailable — {absence['reason']}.")
    else:
        lines.append("**not-found** (absent from inspected material):")
        lines.append("")
        lines += [f"- {item}" for item in absence["not_found"]] or ["None."]
        lines += ["", "**indeterminate** (absence not decidable):", ""]
        lines += [
            f"- {entry['item']} — {entry['reason']}"
            for entry in absence["indeterminate"]
        ] or ["None."]

    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in ledger["warnings"]] or ["None."]
    return "\n".join(lines) + "\n"


def _findings_caveats(findings_doc: dict[str, Any]) -> list[str]:
    """Qualify the findings list whenever it does not cover everything.

    A bare count reads as exhaustive. Gating this on `complete` alone was not
    enough: a run can be complete and still have read almost nothing, because
    `partial` and `uninspectable` units are recorded limitations rather than
    unfinished work.
    """
    coverage = findings_doc.get("coverage") or {}
    units = coverage.get("units", 1.0)
    warnings = findings_doc.get("warnings") or []

    caveats: list[str] = []
    if not findings_doc["complete"]:
        caveats.append("the run is not complete — see the ledger's dispositions")
    if isinstance(units, (int, float)) and units < 1.0:
        caveats.append(
            f"only {units * 100:.1f}% of in-scope units were read in full "
            f"({coverage.get('bytes', 0.0) * 100:.1f}% by byte)"
        )
    if warnings:
        caveats.append(f"{len(warnings)} warning(s) recorded in the coverage ledger")
    if not caveats:
        return []

    lines = ["> Read these findings against the coverage ledger:", ">"]
    lines += [f"> - {caveat}" for caveat in caveats]
    lines += [">", "> Material that was not read may contain more.", ""]
    return lines


def render_findings_markdown(findings_doc: dict[str, Any]) -> str:
    totals = findings_doc["totals"]
    lines = [
        "# Findings",
        "",
        f"{totals['findings']} finding(s).",
        "",
    ]
    lines += _findings_caveats(findings_doc)
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for finding in findings_doc["findings"]:
        for tag in str(finding["tags"]).split(","):
            by_tag.setdefault(tag or "UNTAGGED", []).append(finding)
    for tag in sorted(by_tag):
        lines += [f"## {tag}", ""]
        for finding in by_tag[tag]:
            lines.append(
                f"- [{finding['significance']}] `{finding['citation']}` "
                f"(shard {finding['shard']})"
            )
            # The continuation block is the substance; a marker line alone tells
            # a reader where to look but not what was found.
            for detail in str(finding.get("body", "")).splitlines():
                if detail.strip():
                    lines.append(f"  {detail.strip()}")
        lines.append("")
    if not by_tag:
        lines.append("None.")
        lines.append("")
    return "\n".join(lines)


def read_expected(path: Path | None) -> list[str]:
    if path is None:
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return items


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--shards", required=True)
    parser.add_argument("--findings-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--expected",
        default=None,
        help="file of expected items, one per line, for absence verdicts",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="exit 0 even when units remain pending or failed",
    )
    args = parser.parse_args(argv)

    try:
        inventory = load_json_file(Path(args.inventory).expanduser(), INVENTORY_SCHEMA)
        inventory_sha256 = inventory_digest(inventory)
        shards = load_json_file(Path(args.shards).expanduser(), SHARDS_SCHEMA)
        expected = read_expected(
            Path(args.expected).expanduser() if args.expected else None
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        ledger, findings_doc, warnings = aggregate(
            inventory,
            inventory_sha256,
            shards,
            Path(args.findings_dir).expanduser(),
            expected,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        out_dir = resolve_output(Path(args.out_dir), inventory)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "coverage.json").write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "findings.json").write_text(
        json.dumps(findings_doc, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "coverage.md").write_text(
        render_coverage_markdown(ledger), encoding="utf-8"
    )
    (out_dir / "findings.md").write_text(
        render_findings_markdown(findings_doc), encoding="utf-8"
    )

    counts = ledger["dispositions"]
    print(
        f"Coverage: {counts[REVIEWED]} reviewed, {counts[PARTIAL]} partial, "
        f"{counts[UNINSPECTABLE]} uninspectable, {counts[OUT_OF_SCOPE]} out of scope, "
        f"{counts[FAILED]} failed, {counts[PENDING]} pending"
    )
    print(
        f"Unit coverage {ledger['coverage']['units'] * 100:.1f}%, "
        f"byte coverage {ledger['coverage']['bytes'] * 100:.1f}% -> {out_dir}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if not ledger["complete"]:
        targets = ledger["shards_to_redispatch"]
        listed = ", ".join(targets) if targets else "none identified"
        print(
            "ERROR: review is incomplete; re-dispatch these shards before "
            f"reporting coverage: {listed}",
            file=sys.stderr,
        )
        return 0 if args.allow_incomplete else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
