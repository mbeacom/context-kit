#!/usr/bin/env python3
"""Validate context-kit handoff structure and caller-supplied freshness anchors."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence

SCHEMA = "context-kit/handoff-v1"
DEFAULT_PATH = ".context-kit/handoff.md"
MAX_BYTES = 32 * 1024
MAX_LINES = 300
MAX_ITEMS_PER_SECTION = 25

REQUIRED_FIELDS = (
    "schema",
    "generated_at",
    "repository",
    "worktree",
    "branch",
    "head",
    "base_ref",
    "base_commit",
    "worktree_state",
)

REQUIRED_SECTIONS = (
    "Scope",
    "Verified Facts",
    "Decisions",
    "Changed Files",
    "Completed Work",
    "Unresolved Items",
    "Next Steps",
    "Validation State",
    "Provenance and Freshness",
)

IDENTITY_FIELDS = ("repository", "branch", "base_ref")
FRESHNESS_FIELDS = ("head", "base_commit", "worktree_state")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]+\}\}")
LIST_ITEM_RE = re.compile(r"^(?:[-*+] |\d+[.)] )")


def _find_repository_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_path(
    argument: str | None,
    environ: Mapping[str, str] = os.environ,
    start: Path | None = None,
) -> Path:
    value = argument or environ.get("CONTEXT_KIT_HANDOFF_PATH") or DEFAULT_PATH
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()

    current = (start or Path.cwd()).resolve()
    base = _find_repository_root(current) or current
    return (base / path).resolve()


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_document(text: str) -> tuple[dict[str, str], list[str], list[str]]:
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines, ["document must begin with YAML frontmatter"]

    try:
        closing = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration:
        return {}, lines, ["frontmatter is missing its closing --- fence"]

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            errors.append(
                f"frontmatter line {line_number} must be a flat key: value scalar"
            )
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = _unquote(raw_value.strip())
        if not key or not value:
            errors.append(f"frontmatter line {line_number} has an empty key or value")
            continue
        if key in metadata:
            errors.append(f"frontmatter field {key!r} is duplicated")
            continue
        metadata[key] = value

    return metadata, lines[closing + 1 :], errors


def _section_bodies(
    body_lines: Sequence[str],
) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    active: str | None = None

    for line in body_lines:
        if line.startswith("## "):
            active = line[3:].strip()
            order.append(active)
            sections.setdefault(active, [])
        elif active is not None:
            sections[active].append(line)

    return sections, order


def validate_document(raw: bytes) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    if len(raw) > MAX_BYTES:
        errors.append(f"artifact is {len(raw)} bytes; maximum is {MAX_BYTES}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {}, [f"artifact is not valid UTF-8: {exc}"]

    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        errors.append(f"artifact has {len(lines)} lines; maximum is {MAX_LINES}")
    if PLACEHOLDER_RE.search(text):
        errors.append("artifact contains unresolved {{...}} template placeholders")

    metadata, body_lines, parse_errors = parse_document(text)
    errors.extend(parse_errors)

    for field in REQUIRED_FIELDS:
        if not metadata.get(field):
            errors.append(f"missing required frontmatter field: {field}")

    if metadata.get("schema") and metadata["schema"] != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")

    generated_at = metadata.get("generated_at")
    if generated_at:
        try:
            parsed_timestamp = datetime.fromisoformat(
                generated_at.replace("Z", "+00:00")
            )
        except ValueError:
            errors.append("generated_at must be an ISO 8601 timestamp")
        else:
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                errors.append("generated_at must include a timezone")

    for field in ("head", "base_commit"):
        value = metadata.get(field)
        if value and not COMMIT_RE.fullmatch(value):
            errors.append(f"{field} must be a 7-64 character hexadecimal commit")

    state = metadata.get("worktree_state")
    if state and state not in {"clean", "dirty"}:
        errors.append("worktree_state must be 'clean' or 'dirty'")

    titles = [line.strip() for line in body_lines if line.startswith("# ")]
    if titles != ["# Context Handoff"]:
        errors.append("document must contain exactly one '# Context Handoff' title")

    sections, order = _section_bodies(body_lines)
    if order != list(REQUIRED_SECTIONS):
        errors.append(
            "level-two sections must appear exactly in this order: "
            + ", ".join(REQUIRED_SECTIONS)
        )

    for section in REQUIRED_SECTIONS:
        content = sections.get(section)
        if content is None:
            errors.append(f"missing required section: {section}")
            continue
        meaningful = [line for line in content if line.strip()]
        if not meaningful:
            errors.append(f"section {section!r} must not be empty; use '- None.'")
            continue
        item_count = sum(bool(LIST_ITEM_RE.match(line)) for line in meaningful)
        if item_count > MAX_ITEMS_PER_SECTION:
            errors.append(
                f"section {section!r} has {item_count} list items; "
                f"maximum is {MAX_ITEMS_PER_SECTION}"
            )

    return metadata, errors


def compare_context(
    metadata: Mapping[str, str],
    current: Mapping[str, str | None],
) -> tuple[list[str], list[str]]:
    mismatches: list[str] = []
    stale: list[str] = []

    for field in IDENTITY_FIELDS:
        observed = current.get(field)
        if observed is not None and metadata.get(field) != observed:
            mismatches.append(
                f"{field} mismatch: saved={metadata.get(field)!r} current={observed!r}"
            )

    for field in FRESHNESS_FIELDS:
        observed = current.get(field)
        if observed is not None and metadata.get(field) != observed:
            stale.append(
                f"{field} stale: saved={metadata.get(field)!r} current={observed!r}"
            )

    return mismatches, stale


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a context-kit handoff artifact."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help=(
            "Artifact path. Defaults to CONTEXT_KIT_HANDOFF_PATH, then "
            f"{DEFAULT_PATH}. Relative paths resolve from the nearest repository root."
        ),
    )
    for field in (*IDENTITY_FIELDS, *FRESHNESS_FIELDS):
        parser.add_argument(f"--current-{field.replace('_', '-')}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = resolve_path(args.path)

    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"INVALID: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    metadata, errors = validate_document(raw)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1

    current = {
        field: getattr(args, f"current_{field}")
        for field in (*IDENTITY_FIELDS, *FRESHNESS_FIELDS)
    }
    mismatches, stale = compare_context(metadata, current)

    if mismatches:
        for message in mismatches:
            print(f"MISMATCH: {message}", file=sys.stderr)
        for message in stale:
            print(f"STALE: {message}", file=sys.stderr)
        return 2

    if stale:
        for message in stale:
            print(f"STALE: {message}", file=sys.stderr)
        return 3

    print(f"VALID: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
