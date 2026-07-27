#!/usr/bin/env python3
"""Enumerate a corpus into deterministic, hashed review units."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable, Sequence

SCHEMA = "context-kit/corpus-inventory-v1"
SNIFF_BYTES = 65536
LOSSY_RATIO = 0.02
DEFAULT_INCLUDE = "**/*"

TEXT = "text"
TEXT_LOSSY = "text-lossy"
BINARY = "binary"
EMPTY = "empty"
UNREADABLE = "unreadable"


def translate_glob(pattern: str) -> re.Pattern[str]:
    """Translate a POSIX-style glob into a regex over `/`-joined paths.

    Supports `*` (within a segment), `?`, `[...]`, and `**` (across segments).
    Implemented locally so behavior does not vary with the Python version.
    """
    index = 0
    length = len(pattern)
    out = ["(?s:"]
    while index < length:
        char = pattern[index]
        if char == "*":
            if pattern[index : index + 2] == "**":
                index += 2
                if pattern[index : index + 1] == "/":
                    index += 1
                    out.append("(?:[^/]+/)*")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            end = index + 1
            if end < length and pattern[end] in "!^":
                end += 1
            if end < length and pattern[end] == "]":
                end += 1
            while end < length and pattern[end] != "]":
                end += 1
            if end >= length:
                out.append(re.escape(char))
            else:
                body = pattern[index + 1 : end]
                if body[:1] in "!^":
                    body = "^" + body[1:]
                out.append(f"[{body}]")
                index = end + 1
                continue
        else:
            out.append(re.escape(char))
        index += 1
    out.append(r")\Z")
    return re.compile("".join(out))


class Scope:
    """Include/exclude rules applied to repository-relative posix paths."""

    def __init__(
        self, include: Sequence[str] | None, exclude: Sequence[str] | None
    ) -> None:
        self.include = list(include) if include else [DEFAULT_INCLUDE]
        self.exclude = list(exclude) if exclude else []
        self._include = [translate_glob(item) for item in self.include]
        self._exclude = [translate_glob(item) for item in self.exclude]

    def in_scope(self, relative: str) -> bool:
        if any(rule.match(relative) for rule in self._exclude):
            return False
        return any(rule.match(relative) for rule in self._include)


def iter_files(
    root: Path, follow_symlinks: bool, errors: list[dict[str, str]]
) -> Iterable[Path]:
    """Yield files under root in deterministic sorted order.

    Directory traversal errors are recorded rather than swallowed. `os.walk`
    ignores them silently by default, which would drop an unreadable subtree
    out of the inventory entirely — and a unit that never enters the denominator
    cannot be reported as unread, so coverage would look complete over a corpus
    that quietly lost files.
    """

    def on_error(exc: OSError) -> None:
        target = Path(exc.filename) if exc.filename else root
        try:
            label = target.resolve().relative_to(root.resolve()).as_posix()
        except (ValueError, OSError):
            label = str(target)
        errors.append({"path": label, "error": exc.strerror or type(exc).__name__})

    walker = os.walk(root, onerror=on_error, followlinks=follow_symlinks)
    for directory, dirnames, filenames in walker:
        current = Path(directory)
        dirnames.sort()
        if not follow_symlinks:
            dirnames[:] = [
                name for name in dirnames if not (current / name).is_symlink()
            ]
        for name in sorted(filenames):
            path = current / name
            if not follow_symlinks and path.is_symlink():
                continue
            yield path


def classify(data: bytes, size: int) -> str:
    if size == 0:
        return EMPTY
    if b"\x00" in data[:SNIFF_BYTES]:
        return BINARY
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        replaced = data.decode("utf-8", errors="replace")
        losses = replaced.count("\ufffd")
        if replaced and losses / len(replaced) <= LOSSY_RATIO:
            return TEXT_LOSSY
        return BINARY
    return TEXT


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_text_unit(data: bytes, max_bytes: int) -> list[tuple[int, int, bytes]]:
    """Split decoded text at line boundaries into <= max_bytes chunks.

    Returns (start_line, end_line, chunk_bytes) triples, 1-indexed inclusive.
    A single line longer than max_bytes is kept whole rather than cut mid-line,
    so a citation always points at a complete line.
    """
    lines = data.splitlines(keepends=True)
    chunks: list[tuple[int, int, bytes]] = []
    start = 1
    buffer: list[bytes] = []
    size = 0
    for offset, line in enumerate(lines, start=1):
        if buffer and size + len(line) > max_bytes:
            chunks.append((start, offset - 1, b"".join(buffer)))
            buffer = []
            size = 0
            start = offset
        buffer.append(line)
        size += len(line)
    if buffer:
        chunks.append((start, len(lines), b"".join(buffer)))
    return chunks


def build_units(
    root: Path,
    scope: Scope,
    follow_symlinks: bool,
    max_unit_bytes: int | None,
    errors: list[dict[str, str]],
) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    for path in iter_files(root, follow_symlinks, errors):
        relative = path.relative_to(root).as_posix()
        if not scope.in_scope(relative):
            units.append(
                {
                    "path": relative,
                    "bytes": _safe_size(path),
                    "sha256": None,
                    "inspectable": None,
                    "in_scope": False,
                    "range": None,
                }
            )
            continue
        units.extend(_scan_unit(path, relative, max_unit_bytes))

    units.sort(key=lambda unit: (unit["path"], _range_start(unit)))
    for index, unit in enumerate(units, start=1):
        unit["id"] = f"u{index:04d}"
    return [_ordered_unit(unit) for unit in units]


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _range_start(unit: dict[str, object]) -> int:
    span = unit.get("range")
    if isinstance(span, dict):
        start = span.get("start")
        if isinstance(start, int):
            return start
    return 0


def _ordered_unit(unit: dict[str, object]) -> dict[str, object]:
    keys = ("id", "path", "bytes", "sha256", "inspectable", "in_scope", "range")
    return {key: unit[key] for key in keys}


def _scan_unit(
    path: Path, relative: str, max_unit_bytes: int | None
) -> list[dict[str, object]]:
    try:
        data = path.read_bytes()
    except OSError:
        return [
            {
                "path": relative,
                "bytes": _safe_size(path),
                "sha256": None,
                "inspectable": UNREADABLE,
                "in_scope": True,
                "range": None,
            }
        ]

    inspectable = classify(data, len(data))
    splittable = inspectable in {TEXT, TEXT_LOSSY}
    if max_unit_bytes and splittable and len(data) > max_unit_bytes:
        return [
            {
                "path": relative,
                "bytes": len(chunk),
                "sha256": sha256_bytes(chunk),
                "inspectable": inspectable,
                "in_scope": True,
                "range": {"kind": "lines", "start": start, "end": end},
            }
            for start, end, chunk in split_text_unit(data, max_unit_bytes)
        ]

    return [
        {
            "path": relative,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "inspectable": inspectable,
            "in_scope": True,
            "range": None,
        }
    ]


def summarize(units: Sequence[dict[str, object]]) -> dict[str, object]:
    in_scope = [unit for unit in units if unit["in_scope"]]
    by_inspectability: dict[str, int] = {}
    for unit in in_scope:
        key = str(unit["inspectable"])
        by_inspectability[key] = by_inspectability.get(key, 0) + 1
    return {
        "units": len(units),
        "bytes": sum(int(unit["bytes"]) for unit in units),
        "in_scope_units": len(in_scope),
        "in_scope_bytes": sum(int(unit["bytes"]) for unit in in_scope),
        "out_of_scope_units": len(units) - len(in_scope),
        "by_inspectability": dict(sorted(by_inspectability.items())),
    }


def build_inventory(
    root: Path,
    scope: Scope,
    follow_symlinks: bool,
    max_unit_bytes: int | None,
    now: datetime | None = None,
) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    units = build_units(root, scope, follow_symlinks, max_unit_bytes, errors)
    generated = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "schema": SCHEMA,
        "generated_at": generated,
        "root": str(root),
        "scope": {
            "include": scope.include,
            "exclude": scope.exclude,
            "follow_symlinks": follow_symlinks,
            "max_unit_bytes": max_unit_bytes,
        },
        "totals": summarize(units),
        "errors": sorted(errors, key=lambda entry: entry["path"]),
        "units": units,
    }


def resolve_output(out: Path, root: Path) -> Path:
    resolved = out.expanduser().resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(
            "refusing to write the inventory inside the corpus root; "
            "use a separate work directory"
        )
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="corpus root directory")
    parser.add_argument("--out", required=True, help="inventory JSON destination")
    parser.add_argument(
        "--include",
        action="append",
        help="glob of paths to review; repeatable (default: everything)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="glob of paths to mark out-of-scope; repeatable",
    )
    parser.add_argument(
        "--max-unit-bytes",
        type=int,
        default=None,
        help="split text units larger than this at line boundaries",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="descend into symlinked files and directories",
    )
    parser.add_argument(
        "--allow-unreadable",
        action="store_true",
        help="record unreadable directories and continue instead of failing",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: corpus root is not a directory: {root}", file=sys.stderr)
        return 2
    if args.max_unit_bytes is not None and args.max_unit_bytes <= 0:
        print("ERROR: --max-unit-bytes must be positive", file=sys.stderr)
        return 2

    try:
        out = resolve_output(Path(args.out), root)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    inventory = build_inventory(
        root,
        Scope(args.include, args.exclude),
        args.follow_symlinks,
        args.max_unit_bytes,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    totals = inventory["totals"]
    assert isinstance(totals, dict)
    print(
        f"Inventory: {totals['in_scope_units']} in-scope units "
        f"({totals['in_scope_bytes']} bytes), "
        f"{totals['out_of_scope_units']} out of scope -> {out}"
    )
    for kind, count in sorted(dict(totals["by_inspectability"]).items()):
        print(f"  {kind}: {count}")

    errors = inventory["errors"]
    assert isinstance(errors, list)
    if errors:
        # A directory that could not be traversed removes its files from the
        # denominator, and a unit that never enters the denominator cannot be
        # reported as unread. Fail loudly rather than produce a plausible-looking
        # inventory that silently understates the corpus.
        print(
            f"ERROR: {len(errors)} directory/directories could not be traversed; "
            "their contents are missing from this inventory",
            file=sys.stderr,
        )
        for entry in errors:
            print(f"  {entry['path']}: {entry['error']}", file=sys.stderr)
        if not args.allow_unreadable:
            print(
                "Fix the permissions, exclude the subtree explicitly, or rerun "
                "with --allow-unreadable to accept a known-incomplete denominator",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
