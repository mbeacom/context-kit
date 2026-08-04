#!/usr/bin/env python3
"""Merge independent per-lens review findings without inflating agreement.

Adjudication is deliberately deterministic and standard-library only. Its job is
to keep three things true of a multi-lens review:

1. A declared lens that produced nothing is *reported*, never averaged away.
2. Two lenses reaching the same finding raise confidence, not count.
3. Two lenses wanting different things in one place surface as a decision for a
   human rather than being silently resolved by a synthesizer.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence

FRAME_SCHEMA = "context-kit/review-frame-v1"
FINDINGS_SCHEMA = "context-kit/review-findings-v1"
LEDGER_SCHEMA = "context-kit/review-ledger-v1"

# Ordered high to low; `_max_severity` relies on this order.
SEVERITIES = ("blocking", "major", "minor", "note")

# Each finding type commits its author to supplying specific fields. This is the
# structural half of the taxonomy: a DEFECT whose author cannot write a
# Falsification is a RISK, and the contract makes that impossible to skip.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "DEFECT": ("problem", "consequence", "falsification", "resolution"),
    "RISK": ("problem", "consequence", "trigger", "resolution"),
    "JUDGMENT": ("problem", "consequence", "resolution"),
    "QUESTION": ("problem", "resolution"),
}
FINDING_TYPES = tuple(REQUIRED_FIELDS)

REQUIRED_SECTIONS = frozenset({"summary", "findings", "coverage"})

FINDING_RE = re.compile(
    r"^-\s*\[(?P<type>[^\]]+)\]\s*"
    r"\[severity:\s*(?P<severity>[^\]]+)\]\s*"
    r"`(?P<citation>[^`]+)`",
    re.IGNORECASE,
)
CANDIDATE_RE = re.compile(r"^-\s*\[")
FIELD_RE = re.compile(r"^\*\*(?P<key>[A-Za-z][A-Za-z ]*):\*\*\s*(?P<value>.*)$")
HEADING_RE = re.compile(r"^##+\s+(?P<title>.+?)\s*$")
TOKEN_RE = re.compile(r"[a-z0-9]+")

# Boilerplate that appears in nearly every finding and would otherwise inflate
# similarity between unrelated problems.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "no",
        "not",
        "of",
        "on",
        "or",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "were",
        "when",
        "which",
        "will",
        "with",
        "would",
    }
)

DEFAULT_MERGE_THRESHOLD = 0.5
DEFAULT_CONFLICT_THRESHOLD = 0.5

EVALUATION_BOUNDARY = (
    "Deterministic merge and collision heuristics only; corroboration and "
    "tradeoff candidates are review signals, not semantic-equivalence claims."
)


def split_bundle(text: str) -> list[str]:
    """Split a bundle holding several concatenated lens reports.

    A worker returns its findings document inline, so an orchestrator often has
    every report in context but none on disk. Requiring one file per lens turned
    the deterministic spine into extra filesystem work, and in practice the
    whole adjudication step got skipped instead. Accepting one bundled file
    makes the honest path the cheap one.

    A document starts at a `---` fence whose first field is `schema:`. Fenced
    code blocks are tracked and ignored so a report quoting the contract does
    not split itself in half.
    """
    lines = text.splitlines()
    starts: list[int] = []
    in_code = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or stripped != "---":
            continue
        following = next(
            (
                lines[j].strip()
                for j in range(index + 1, len(lines))
                if lines[j].strip()
            ),
            "",
        )
        if following.startswith("schema:"):
            starts.append(index)
    if not starts:
        return []
    bounds = starts + [len(lines)]
    return [
        "\n".join(lines[bounds[i] : bounds[i + 1]]).strip("\n")
        for i in range(len(starts))
    ]


class AdjudicationError(Exception):
    """A degraded review. Reported as degraded, never quietly cleaned up."""


def load_json_file(path: Path, schema: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdjudicationError(
            f"{path.name} could not be read as JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise AdjudicationError(f"{path.name} must be a JSON object")
    if data.get("schema") != schema:
        raise AdjudicationError(f"{path.name} schema must be `{schema}`")
    return data


def resolve_output(destination: Path, findings_dir: Path) -> Path:
    """Refuse to write the report into the findings directory.

    A ledger written beside the lens reports is parsed as a lens report by the
    next run, which would let the review grade its own output.
    """
    resolved = destination.expanduser().resolve()
    source = findings_dir.expanduser().resolve()
    if resolved == source or source in resolved.parents:
        raise AdjudicationError(
            f"refusing to write inside the findings directory ({source}); use a "
            "separate report directory so a re-run does not read its own output"
        )
    return resolved


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse a minimal frontmatter block whose values are JSON or bare scalars.

    Deliberately not a YAML parser: the findings header is a fixed, small shape,
    and a third-party requirement here would break a standard-library pipeline.
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
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            current = match.group("title").strip().lower()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def normalize_citation(raw: str) -> str:
    return " ".join(raw.strip().strip("`'\" ").split())


def content_tokens(text: str) -> frozenset[str]:
    return frozenset(
        token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS
    )


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of content tokens.

    Two empty texts are treated as maximally similar so a pair of findings that
    both omit an optional field never registers as a disagreement.
    """
    a, b = content_tokens(left), content_tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _max_severity(values: Iterable[str]) -> str:
    ranked = [v for v in values if v in SEVERITIES]
    if not ranked:
        return SEVERITIES[-1]
    return min(ranked, key=SEVERITIES.index)


def parse_findings_section(
    lines: Sequence[str],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Return parsed findings, malformed-bullet count, and stray content.

    An unparsed bullet is counted rather than dropped: a lens that wrote the
    marker slightly differently should surface a contract error, not vanish.

    Stray content is any non-blank line outside a finding block that is not the
    `None.` placeholder. Ignoring it would let a truncated or prose-only section
    return zero findings and be reported as a clean lens, which is the one
    error this pipeline cannot otherwise detect.
    """
    findings: list[dict[str, Any]] = []
    unparsed = 0
    stray: list[str] = []
    current: dict[str, Any] | None = None
    field_key: str | None = None

    def flush() -> None:
        nonlocal current, field_key
        if current is not None:
            findings.append(current)
        current, field_key = None, None

    for line in lines:
        stripped = line.strip()
        if CANDIDATE_RE.match(stripped):
            flush()
            match = FINDING_RE.match(stripped)
            if match is None:
                unparsed += 1
                continue
            current = {
                "type": match.group("type").strip().upper(),
                "severity": match.group("severity").strip().lower(),
                "citation": normalize_citation(match.group("citation")),
                "fields": {},
                "text": stripped,
            }
            continue
        if not stripped:
            continue
        if current is None:
            if stripped.rstrip(".").strip().lower() != "none":
                stray.append(stripped)
            continue
        field = FIELD_RE.match(stripped)
        if field is not None:
            field_key = field.group("key").strip().lower()
            current["fields"][field_key] = field.group("value").strip()
            continue
        if field_key is not None:  # continuation of the active field
            current["fields"][field_key] = (
                f"{current['fields'][field_key]} {stripped}".strip()
            )
            continue
        stray.append(stripped)
    flush()
    return findings, unparsed, stray


def read_lens_report(
    path: Path, frame_artifact: str = ""
) -> tuple[dict[str, Any], list[str]]:
    """Read and parse one lens report file."""
    label = path.name
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {}, [f"{label}: unreadable ({exc})"]
    return parse_lens_report(text, label, frame_artifact)


def parse_lens_report(
    text: str, label: str, frame_artifact: str = ""
) -> tuple[dict[str, Any], list[str]]:
    """Parse one lens report, returning the report and its contract errors."""
    errors: list[str] = []

    fields, body = parse_frontmatter(text)
    if fields is None:
        return {}, [f"{label}: missing or unterminated frontmatter"]
    if fields.get("schema") != FINDINGS_SCHEMA:
        errors.append(f"{label}: schema must be `{FINDINGS_SCHEMA}`")
    lens = fields.get("lens")
    if not isinstance(lens, str) or not lens.strip():
        return {}, errors + [f"{label}: missing `lens`"]
    lens = lens.strip()

    # A report from another revision cites lines that may not exist at the
    # frame's revision, so merging it would present stale locations — and stale
    # corroboration — under this panel's artifact.
    artifact = fields.get("artifact")
    artifact = artifact.strip() if isinstance(artifact, str) else ""
    if not artifact:
        errors.append(f"{label}: missing `artifact`")
    elif frame_artifact and artifact != frame_artifact:
        errors.append(
            f"{label}: artifact `{artifact}` does not match the frame's "
            f"`{frame_artifact}`"
        )

    sections = split_sections(body)
    missing = sorted(REQUIRED_SECTIONS - set(sections))
    if missing:
        # A truncated report is a failed lens, not a terse one: its silence
        # cannot be read as "nothing to report".
        errors.append(f"{label}: missing required section(s) {', '.join(missing)}")

    findings, unparsed, stray = parse_findings_section(sections.get("findings", []))
    if unparsed:
        errors.append(
            f"{label}: {unparsed} finding bullet(s) did not match the contract"
        )
    if stray:
        errors.append(
            f"{label}: Findings section has {len(stray)} line(s) outside any "
            f"finding block, starting with {stray[0][:60]!r}"
        )

    scope_reviewed, reviewed_errors = _string_list(
        fields.get("scope_reviewed"), f"{label}.scope_reviewed"
    )
    scope_skipped, skipped_errors = _region_list(
        fields.get("scope_skipped"), f"{label}.scope_skipped"
    )
    errors.extend(reviewed_errors + skipped_errors)

    for index, finding in enumerate(findings, start=1):
        where = f"{label} finding {index}"
        ftype = finding["type"]
        # Attribute every finding to its lens before validating, so a rejected
        # finding is still reportable rather than an unattributed orphan.
        finding["lens"] = lens
        finding["valid"] = True
        if ftype not in FINDING_TYPES:
            errors.append(f"{where}: unknown type `{ftype}`")
            finding["valid"] = False
            continue
        if finding["severity"] not in SEVERITIES:
            errors.append(f"{where}: unknown severity `{finding['severity']}`")
            finding["valid"] = False
        if not finding["citation"]:
            errors.append(f"{where}: missing citation")
            finding["valid"] = False
        elif finding["citation"].strip().lower() == "none" and ftype != "QUESTION":
            # Only a QUESTION may ask about a thing that has no location. A
            # DEFECT cited as `none` would reach verify with nowhere to look.
            errors.append(
                f"{where}: citation `none` is only valid for a QUESTION, not {ftype}"
            )
            finding["valid"] = False
        for required in REQUIRED_FIELDS[ftype]:
            if not finding["fields"].get(required):
                errors.append(f"{where}: {ftype} requires a non-empty `{required}`")
                finding["valid"] = False

    report = {
        "lens": lens,
        "artifact": artifact,
        "scope_reviewed": scope_reviewed,
        "scope_skipped": scope_skipped,
        "summary": "\n".join(sections.get("summary", [])).strip(),
        "coverage": "\n".join(sections.get("coverage", [])).strip(),
        "findings": findings,
        "source": label,
    }
    return report, errors


def _string_list(value: Any, label: str) -> tuple[list[str], list[str]]:
    """Coerce a JSON string list, reporting malformed shapes rather than
    dropping them.

    Coverage is what bounds how a reader may interpret silence, so a scope
    field that silently becomes empty understates what went unreviewed.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [f"{label} must be a JSON list of strings"]
    out: list[str] = []
    errors: list[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        else:
            errors.append(f"{label} entry {item!r} must be a string")
    return out, errors


def _region_list(value: Any, label: str) -> tuple[list[dict[str, str]], list[str]]:
    """Coerce skipped-region entries, reporting malformed shapes.

    A dropped skipped-region makes an unreviewed area invisible, which is
    exactly the misreading the Coverage section exists to prevent.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [f"{label} must be a JSON list of objects"]
    out: list[dict[str, str]] = []
    errors: list[str] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("region"), str):
            errors.append(f"{label} entry {item!r} must be an object with a `region`")
            continue
        out.append(
            {
                "region": item["region"],
                "reason": str(item.get("reason", "unspecified")),
            }
        )
    return out, errors


def entry_id(ftype: str, citation: str, problem: str) -> str:
    payload = "|".join([ftype, citation, " ".join(sorted(content_tokens(problem)))])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def merge_findings(
    findings: Sequence[dict[str, Any]], merge_threshold: float
) -> list[dict[str, Any]]:
    """Cluster findings that share a type and citation and describe one problem.

    Clustering compares each candidate against a cluster's first member rather
    than any member. Single-linkage chaining would make the result depend on
    input order; comparing against a fixed representative keeps it stable.
    """
    ordered = sorted(
        findings, key=lambda f: (f["type"], f["citation"], f["lens"], f["text"])
    )
    clusters: list[list[dict[str, Any]]] = []
    for finding in ordered:
        placed = False
        for cluster in clusters:
            head = cluster[0]
            if (
                head["type"] != finding["type"]
                or head["citation"] != finding["citation"]
            ):
                continue
            score = similarity(
                head["fields"].get("problem", ""), finding["fields"].get("problem", "")
            )
            if score >= merge_threshold:
                cluster.append(finding)
                placed = True
                break
        if not placed:
            clusters.append([finding])

    entries: list[dict[str, Any]] = []
    for cluster in clusters:
        head = cluster[0]
        lenses = sorted({member["lens"] for member in cluster})
        entries.append(
            {
                "id": entry_id(
                    head["type"], head["citation"], head["fields"].get("problem", "")
                ),
                "type": head["type"],
                "citation": head["citation"],
                # The highest severity any lens asserted. Averaging severity
                # would let a `note` from one lens dilute another's `blocking`.
                "severity": _max_severity(member["severity"] for member in cluster),
                "lenses": lenses,
                "corroborated": len(lenses) > 1,
                "raised_by": len(cluster),
                "fields": head["fields"],
                # Every member's own resolution is retained. Agreement on a
                # problem does not imply agreement on the fix, and keeping only
                # the head's resolution would discard a dissenting lens's
                # position before conflict detection could ever see it.
                "positions": [
                    {
                        "lens": member["lens"],
                        "severity": member["severity"],
                        "resolution": member["fields"].get("resolution", ""),
                    }
                    for member in cluster
                ],
                "variants": [
                    member["fields"].get("problem", "")
                    for member in cluster[1:]
                    if member["fields"].get("problem", "")
                    != head["fields"].get("problem", "")
                ],
            }
        )
    entries.sort(
        key=lambda e: (SEVERITIES.index(e["severity"]), e["type"], e["citation"])
    )
    return entries


def find_tradeoff_candidates(
    entries: Sequence[dict[str, Any]], conflict_threshold: float
) -> list[dict[str, Any]]:
    """Flag two lenses wanting different things at the same location.

    Comparison runs over individual lens *positions*, not over merged entries,
    so a conflict is caught whether the lenses disagreed about separate problems
    or agreed on one problem and split on the fix. Comparing merged entries
    alone would let corroboration hide the second case entirely.

    Reported as candidates: deciding whether two prose resolutions genuinely
    contradict is not a deterministic operation, and the value here is surfacing
    the collision rather than letting a synthesizer pick a winner.
    """
    positions: list[dict[str, Any]] = []
    for entry in entries:
        for position in entry["positions"]:
            positions.append(
                {
                    "id": entry["id"],
                    "citation": entry["citation"],
                    "type": entry["type"],
                    "lens": position["lens"],
                    "severity": position["severity"],
                    "resolution": position["resolution"],
                }
            )

    candidates: list[dict[str, Any]] = []
    for i, left in enumerate(positions):
        for right in positions[i + 1 :]:
            if left["citation"] != right["citation"]:
                continue
            if left["lens"] == right["lens"]:
                continue  # one lens cannot disagree with itself
            score = similarity(left["resolution"], right["resolution"])
            if score >= conflict_threshold:
                continue
            candidates.append(
                {
                    "citation": left["citation"],
                    "resolution_similarity": round(score, 3),
                    # True when both lenses agreed the problem was the same and
                    # split only on the fix — the case a merged view hides.
                    "within_finding": left["id"] == right["id"],
                    "positions": [
                        {
                            "id": position["id"],
                            "lenses": [position["lens"]],
                            "type": position["type"],
                            "severity": position["severity"],
                            "resolution": position["resolution"],
                        }
                        for position in (left, right)
                    ],
                }
            )
    candidates.sort(
        key=lambda c: (
            c["citation"],
            c["positions"][0]["id"],
            c["positions"][0]["lenses"][0],
            c["positions"][1]["lenses"][0],
        )
    )
    return candidates


def _counts(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def adjudicate(
    frame: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    merge_threshold: float,
    conflict_threshold: float,
) -> dict[str, Any]:
    declared = [
        lens
        for lens in _string_list(frame.get("expected_lenses"), "frame.expected_lenses")[
            0
        ]
        if lens.strip()
    ]
    reported = sorted(reports)
    missing = sorted(set(declared) - set(reported))
    undeclared = sorted(set(reported) - set(declared))

    raw = [f for lens in reported for f in reports[lens]["findings"]]
    # A finding that failed the contract is reported as a rejection, never
    # merged: letting it through would put an unfalsified defect in the ledger.
    accepted = [f for f in raw if f.get("valid")]
    entries = merge_findings(accepted, merge_threshold)
    tradeoffs = find_tradeoff_candidates(entries, conflict_threshold)

    # A lens that produced findings but only ever asked QUESTIONs never actually
    # judged anything — it lacked the context or tooling to reach a verdict.
    # Without this flag its zero defects read as "found no defects", when the
    # truthful reading is "could not look". A lens with no findings at all is
    # excluded: that is a genuine clean result, not a capability gap.
    question_dominated = sorted(
        lens
        for lens in reported
        if [f for f in accepted if f["lens"] == lens]
        and all(f["type"] == "QUESTION" for f in accepted if f["lens"] == lens)
    )

    return {
        "schema": LEDGER_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frame": {
            "artifact": frame.get("artifact", ""),
            "decision": frame.get("decision", ""),
            "stakes": frame.get("stakes", ""),
        },
        "lenses": {
            "declared": declared,
            "reported": reported,
            "missing": missing,
            "undeclared": undeclared,
            "question_dominated": question_dominated,
        },
        "thresholds": {
            "merge": merge_threshold,
            "conflict": conflict_threshold,
        },
        "counts": {
            "raw_findings": len(raw),
            "rejected_findings": len(raw) - len(accepted),
            "merged_findings": len(entries),
            "by_type": _counts(e["type"] for e in entries),
            "by_severity": _counts(e["severity"] for e in entries),
            "by_lens": _counts(f["lens"] for f in accepted),
            "corroborated": sum(1 for e in entries if e["corroborated"]),
        },
        "findings": entries,
        "tradeoff_candidates": tradeoffs,
        "routing": {
            # DEFECT is an assertion this plugin refuses to settle itself.
            "verify": [e["id"] for e in entries if e["type"] == "DEFECT"],
            # Risks are queued for triage, not routed. Only a risk whose trigger
            # is *observable* can be settled by running something, and whether a
            # prose trigger is observable is a judgment the routing step makes —
            # a maintenance or adoption risk has a real trigger that no command
            # can reproduce. Presenting these as routed would overstate what
            # runtime evidence is able to settle.
            "risk_triage": [e["id"] for e in entries if e["type"] == "RISK"],
            "answer": [e["id"] for e in entries if e["type"] == "QUESTION"],
        },
        "coverage": {
            lens: {
                "reviewed": reports[lens]["scope_reviewed"],
                "skipped": reports[lens]["scope_skipped"],
                "notes": reports[lens]["coverage"],
            }
            for lens in reported
        },
        "evaluation_boundary": EVALUATION_BOUNDARY,
    }


def render_markdown(ledger: dict[str, Any]) -> str:
    lines: list[str] = ["# Deep review", ""]
    frame = ledger["frame"]
    lines.append(f"- **Artifact:** {frame['artifact'] or 'unspecified'}")
    lines.append(f"- **Decision:** {frame['decision'] or 'unspecified'}")
    lines.append(f"- **Stakes:** {frame['stakes'] or 'unspecified'}")
    counts = ledger["counts"]
    lines.append(
        f"- **Findings:** {counts['merged_findings']} merged from "
        f"{counts['raw_findings']} raised ({counts['corroborated']} corroborated)"
    )
    lines.append("")

    lenses = ledger["lenses"]
    if lenses["missing"] or lenses.get("question_dominated"):
        lines += ["## Degraded review", ""]
    if lenses["missing"]:
        lines += [
            "These declared lenses returned no usable report. This review says "
            "nothing about their charters — it does **not** report them clean:",
            "",
        ]
        lines += [f"- `{lens}`" for lens in lenses["missing"]]
        lines.append("")
    if lenses.get("question_dominated"):
        lines += [
            "These lenses only asked questions, so they judged nothing. Their "
            "zero defects mean *could not look*, not *nothing to find* — answer "
            "the questions or give the lens the access it lacked, then re-run it:",
            "",
        ]
        lines += [f"- `{lens}`" for lens in lenses["question_dominated"]]
        lines.append("")

    lines += ["## Findings", ""]
    if not ledger["findings"]:
        lines += ["None.", ""]
    for entry in ledger["findings"]:
        mark = " (corroborated)" if entry["corroborated"] else ""
        lines.append(
            f"### [{entry['type']}] [{entry['severity']}] `{entry['citation']}`{mark}"
        )
        lines.append("")
        lines.append(f"- **Lenses:** {', '.join(entry['lenses'])}")
        for key in ("problem", "consequence", "falsification", "trigger", "resolution"):
            value = entry["fields"].get(key)
            if value:
                lines.append(f"- **{key.capitalize()}:** {value}")
        for variant in entry["variants"]:
            lines.append(f"- **Also described as:** {variant}")
        lines.append("")

    lines += ["## Unresolved tradeoffs", ""]
    if not ledger["tradeoff_candidates"]:
        lines += ["None.", ""]
    for candidate in ledger["tradeoff_candidates"]:
        scope = (
            " — same problem, opposing fixes" if candidate.get("within_finding") else ""
        )
        lines.append(f"### `{candidate['citation']}`{scope}")
        lines.append("")
        for position in candidate["positions"]:
            lines.append(
                f"- **{', '.join(position['lenses'])}** ({position['type']}, "
                f"{position['severity']}): {position['resolution']}"
            )
        lines.append("")
        lines.append("Owner decision required; not auto-resolved.")
        lines.append("")

    lines += ["## Routing", ""]
    routing = ledger["routing"]
    lines.append(
        f"- **To `verify`:** {len(routing['verify'])} defect claim(s) — unverified "
        "until a verdict returns."
    )
    lines.append(
        f"- **Risks to triage:** {len(routing['risk_triage'])} risk(s) with a stated "
        "trigger. Only those whose trigger is observable can go to "
        "`runtime-evidence`; classify them at the routing step."
    )
    lines.append(f"- **Awaiting an answer:** {len(routing['answer'])} question(s).")
    lines.append("")

    lines += ["## Coverage", ""]
    if not ledger["coverage"]:
        lines += ["None.", ""]
    for lens, coverage in sorted(ledger["coverage"].items()):
        reviewed = ", ".join(coverage["reviewed"]) or "unspecified"
        lines.append(f"- **{lens}** — reviewed: {reviewed}")
        for skipped in coverage["skipped"]:
            lines.append(f"  - skipped `{skipped['region']}`: {skipped['reason']}")
    lines.append("")
    lines.append(
        "A finding list without this section reads as approval of everything it "
        "does not mention."
    )
    lines.append("")
    return "\n".join(lines)


def collect_reports(
    findings_dir: Path | None = None,
    frame_artifact: str = "",
    findings_file: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Gather lens reports from a directory of files or one bundled file."""
    parsed: list[tuple[str, dict[str, Any], list[str]]] = []

    if findings_file is not None:
        if not findings_file.is_file():
            raise AdjudicationError(f"findings file not found: {findings_file}")
        try:
            bundle = findings_file.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise AdjudicationError(
                f"{findings_file.name} could not be read: {exc}"
            ) from exc
        documents = split_bundle(bundle)
        if not documents:
            raise AdjudicationError(
                f"{findings_file.name} contains no `{FINDINGS_SCHEMA}` document; a "
                "bundle holds each lens report verbatim, frontmatter included"
            )
        for index, document in enumerate(documents, start=1):
            label = f"{findings_file.name}[{index}]"
            report, report_errors = parse_lens_report(document, label, frame_artifact)
            parsed.append((label, report, report_errors))
    else:
        if findings_dir is None or not findings_dir.is_dir():
            raise AdjudicationError(f"findings directory not found: {findings_dir}")
        for path in sorted(findings_dir.glob("*.md")):
            report, report_errors = read_lens_report(path, frame_artifact)
            parsed.append((path.name, report, report_errors))

    reports: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for label, report, report_errors in parsed:
        errors.extend(report_errors)
        if not report:
            continue
        lens = report["lens"]
        if lens in reports:
            errors.append(
                f"{label}: lens `{lens}` already reported by {reports[lens]['source']}"
            )
            continue
        reports[lens] = report
    return reports, errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate independent per-lens review findings."
    )
    parser.add_argument("--frame", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--findings-dir",
        type=Path,
        help="directory holding one <lens>.md report per lens",
    )
    source.add_argument(
        "--findings-file",
        type=Path,
        help=(
            "one file holding every lens report concatenated verbatim; use this "
            "when workers returned their documents inline"
        ),
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--merge-threshold", type=float, default=DEFAULT_MERGE_THRESHOLD
    )
    parser.add_argument(
        "--conflict-threshold", type=float, default=DEFAULT_CONFLICT_THRESHOLD
    )
    args = parser.parse_args(argv)

    for name, value in (
        ("--merge-threshold", args.merge_threshold),
        ("--conflict-threshold", args.conflict_threshold),
    ):
        if not 0.0 <= value <= 1.0:
            print(f"ERROR: {name} must be between 0 and 1", file=sys.stderr)
            return 2

    try:
        frame = load_json_file(args.frame, FRAME_SCHEMA)
        # Only directory mode can re-read its own output on a later run; a
        # bundle names exactly one file, so it needs no glob-collision guard.
        out_dir = (
            resolve_output(args.out_dir, args.findings_dir)
            if args.findings_dir is not None
            else args.out_dir.expanduser().resolve()
        )
        frame_artifact = frame.get("artifact")
        frame_artifact = (
            frame_artifact.strip() if isinstance(frame_artifact, str) else ""
        )
        reports, errors = collect_reports(
            args.findings_dir, frame_artifact, args.findings_file
        )
    except AdjudicationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    declared, declared_errors = _string_list(
        frame.get("expected_lenses"), "frame.expected_lenses"
    )
    errors.extend(declared_errors)
    if not declared:
        print(
            "ERROR: frame must declare a non-empty `expected_lenses` roster; without "
            "one, a crashed lens is indistinguishable from a lens that found nothing",
            file=sys.stderr,
        )
        return 1

    ledger = adjudicate(frame, reports, args.merge_threshold, args.conflict_threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (out_dir / "review.md").write_text(render_markdown(ledger), encoding="utf-8")

    for lens in ledger["lenses"]["missing"]:
        errors.append(f"declared lens `{lens}` produced no report")
    for lens in ledger["lenses"]["undeclared"]:
        errors.append(f"lens `{lens}` reported but is not in the frame roster")

    counts = ledger["counts"]
    print(
        f"Adjudicated {counts['raw_findings']} finding(s) from "
        f"{len(ledger['lenses']['reported'])}/{len(declared)} declared lens(es) into "
        f"{counts['merged_findings']} entries "
        f"({counts['corroborated']} corroborated, "
        f"{len(ledger['tradeoff_candidates'])} tradeoff candidate(s))"
    )
    print(f"Wrote {out_dir / 'ledger.json'} and {out_dir / 'review.md'}")

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        print(
            f"\nFAIL: {len(errors)} problem(s); the review is degraded. Re-dispatch "
            "the named lens rather than reporting a partial panel as complete.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
