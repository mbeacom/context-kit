#!/usr/bin/env python3
"""Validate the YAML frontmatter of every slash command shipped by a plugin.

Hosts reject a command whose frontmatter field parses to the wrong YAML type,
and the failure is fatal at load time rather than merely degraded: an unquoted
``argument-hint: [artifact-path]`` is a YAML *flow sequence*, not a string, so
the host refuses the command with ``argument-hint must be a string``.

Nothing else in this repo validates ``commands/*.md``. ``check-skills.sh`` only
covers skills and agents, and its line-oriented parser reads ``[x]`` as the
literal text ``"[x]"``, so it cannot see this class of breakage at all.

This gate resolves the YAML *type* each value would take, using only the
standard library (PyYAML is not a dependency of this repo), and fails when:

  - frontmatter is missing or never closed
  - a plain scalar contains ``": "``, which is a YAML parse error
  - a quoted scalar is unterminated or carries trailing junk
  - a string-typed field would parse as a sequence, mapping, bool, number,
    null, or timestamp
  - ``disable-model-invocation`` is not a boolean
  - ``description`` is missing or empty
  - an unrecognized top-level key is present (a typo such as ``argument_hint``
    is silently ignored by hosts, which is the same failure mode being fixed)

Extend ``STRING_FIELDS`` / ``BOOL_FIELDS`` when a host adds a frontmatter field.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FENCE = "---"

STRING_FIELDS = frozenset(
    {
        "name",
        "description",
        "argument-hint",
        "allowed-tools",
        "model",
    }
)
BOOL_FIELDS = frozenset({"disable-model-invocation"})
KNOWN_FIELDS = STRING_FIELDS | BOOL_FIELDS
REQUIRED_FIELDS = ("description",)

KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:(?P<rest>.*)$")
# A `#` opens a comment only at the start of a value or after whitespace.
COMMENT_RE = re.compile(r"(?:^|\s)#")
QUOTES = ("'", '"')
BLOCK_INDICATORS = ("|", ">")

# Ported verbatim from PyYAML's implicit resolvers (YAML 1.1), which is what the
# hosts embed. Parity is verified case-by-case in tests/test_command_frontmatter.py.
# Deliberate consequences: `1e3` and `1.0e3` are strings (the exponent needs an
# explicit sign), `0o17` is a string (YAML 1.1 octal is `017`), and `y`/`n` are
# strings (PyYAML omits the single-letter booleans).
BOOL_RE = re.compile(
    r"^(?:yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$"
)
NULL_RE = re.compile(r"^(?:~|null|Null|NULL|)$")
INT_RE = re.compile(
    r"""^(?:
        [-+]?0b[0-1_]+
      | [-+]?0[0-7_]+
      | [-+]?(?:0|[1-9][0-9_]*)
      | [-+]?0x[0-9a-fA-F_]+
      | [-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+
    )$""",
    re.VERBOSE,
)
FLOAT_RE = re.compile(
    r"""^(?:
        [-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?
      | \.[0-9_]+(?:[eE][-+][0-9]+)?
      | [-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
      | [-+]?\.(?:inf|Inf|INF)
      | \.(?:nan|NaN|NAN)
    )$""",
    re.VERBOSE,
)
# A bare `2026-01-01` silently becomes a `datetime.date` rather than the string
# an author intended. The date-only form requires two-digit month and day.
TIMESTAMP_RE = re.compile(
    r"""^(?:
        [0-9]{4}-[0-9]{2}-[0-9]{2}
      | [0-9]{4}-[0-9]{1,2}-[0-9]{1,2}
        (?:[Tt]|[\ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]*)?
        (?:[\ \t]*(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?
    )$""",
    re.VERBOSE,
)


@dataclass
class Entry:
    """One top-level frontmatter key: its inline value plus its indented body."""

    inline: str
    line_number: int
    body: list[str] = field(default_factory=list)


@dataclass
class Frontmatter:
    entries: dict[str, Entry]
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    errors: list[str]
    command_count: int = 0


def _strip_comment(value: str) -> str:
    """Drop a YAML comment from a plain (unquoted) scalar.

    A value that is *only* a comment collapses to the empty string, which YAML
    resolves to null — the same wrong-type failure as any other mismatch.
    """
    match = COMMENT_RE.search(value)
    return value[: match.start()].rstrip() if match else value


def _closing_quote(value: str) -> int | None:
    """Index just past the closing quote of ``value``, or None if unterminated.

    Callers must confirm ``value`` opens with a quote. Double-quoted scalars
    honour ``\\`` escapes; single-quoted scalars use ``''`` for a literal quote.
    """
    quote = value[0]
    index = 1
    length = len(value)
    while index < length:
        char = value[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if char == quote:
            if quote == "'" and value[index + 1 : index + 2] == "'":
                index += 2
                continue
            return index + 1
        index += 1
    return None


def resolve_type(raw: str) -> str:
    """Return the YAML node type a frontmatter value resolves to.

    One of: ``str``, ``seq``, ``map``, ``bool``, ``int``, ``float``, ``null``,
    ``timestamp``, or ``malformed`` for a value YAML cannot parse at all.
    """
    value = raw.strip()
    if value[:1] in QUOTES:
        end = _closing_quote(value)
        if end is None:
            return "malformed"
        trailing = value[end:].strip()
        if trailing and not trailing.startswith("#"):
            return "malformed"
        return "str"
    if value[:1] in BLOCK_INDICATORS:  # block scalar; the body follows, indented
        return "str"
    value = _strip_comment(value).strip()
    if value.startswith("["):
        return "seq"
    if value.startswith("{"):
        return "map"
    if value.startswith("*"):
        # An alias with no anchor to resolve, which is all frontmatter can hold.
        return "malformed"
    # `&anchor value` and `!!tag value` resolve to the value they decorate, so
    # they are deliberately not special-cased; the resolvers below see the whole
    # string and fall through to `str`, matching PyYAML.
    if NULL_RE.match(value):
        return "null"
    if BOOL_RE.match(value):
        return "bool"
    if INT_RE.match(value):
        return "int"
    if FLOAT_RE.match(value):
        return "float"
    if TIMESTAMP_RE.match(value):
        return "timestamp"
    return "str"


def _significant(body: list[str]) -> list[str]:
    """Body lines that carry a value, ignoring blanks and whole-line comments."""
    return [
        stripped
        for stripped in (line.strip() for line in body)
        if stripped and not stripped.startswith("#")
    ]


def _body_type(body: list[str]) -> str:
    """Type of a node whose value lives entirely in its indented body."""
    lines = _significant(body)
    if not lines:
        return "null"
    first = lines[0]
    if first == "-" or first.startswith("- "):
        return "seq"
    if KEY_RE.match(first):
        return "map"
    return "str"


def entry_type(entry: Entry) -> str:
    """Type of a whole frontmatter entry: inline value plus indented body."""
    inline = entry.inline.strip()
    if not inline:
        return _body_type(entry.body)
    kind = resolve_type(inline)
    if kind == "null":  # inline was empty or comment-only, so the body decides
        return _body_type(entry.body)
    plain = kind == "str" and inline[:1] not in QUOTES + BLOCK_INDICATORS
    if plain and any(KEY_RE.match(line) for line in _significant(entry.body)):
        # `key: text` followed by an indented `other: value` is the YAML error
        # "mapping values are not allowed in this context".
        return "malformed"
    return kind


def parse_frontmatter(text: str) -> Frontmatter | None:
    """Parse top-level frontmatter, or return None when absent or unclosed.

    Each top-level key keeps its inline value and its indented body separately,
    so a nested mapping or sequence stays distinguishable from a wrapped plain
    scalar or a block scalar. Folding them together would let
    ``description:`` + an indented ``text: value`` — a mapping — pass as a string.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None
    parsed = Frontmatter(entries={})
    active: Entry | None = None
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == FENCE:
            return parsed
        if not line.strip():
            continue
        if line[0] in (" ", "\t"):
            if active is not None:
                active.body.append(line)
            continue
        match = KEY_RE.match(line)
        if not match:
            parsed.errors.append(f"line {number}: not a `key: value` mapping: {line!r}")
            continue
        key = match.group("key")
        rest = match.group("rest")
        if rest and not rest.startswith((" ", "\t")):
            # `key:value` is a single plain scalar in YAML, not a mapping.
            parsed.errors.append(
                f"line {number}: `{key}:` needs a space after the colon"
            )
            continue
        if key in parsed.entries:
            parsed.errors.append(f"line {number}: duplicate key `{key}`")
        value = rest.strip()
        if value[:1] not in QUOTES + BLOCK_INDICATORS + ("[", "{"):
            plain = _strip_comment(value)
            if ": " in plain or plain.endswith(":"):
                parsed.errors.append(
                    f"line {number}: `{key}` value contains an unquoted `:` "
                    f"and is a YAML parse error; quote it"
                )
        active = Entry(inline=value, line_number=number)
        parsed.entries[key] = active
    parsed.errors.append("frontmatter is never closed by a `---` fence")
    return parsed


def validate_command(path: Path, label: str, errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{label}: cannot read file: {exc}")
        return

    parsed = parse_frontmatter(text)
    if parsed is None:
        errors.append(f"{label}: missing YAML frontmatter")
        return
    for message in parsed.errors:
        errors.append(f"{label}: {message}")

    for key, entry in parsed.entries.items():
        if key not in KNOWN_FIELDS:
            errors.append(
                f"{label}: unknown frontmatter key `{key}` "
                f"(known: {', '.join(sorted(KNOWN_FIELDS))})"
            )
            continue
        kind = entry_type(entry)
        shown = entry.inline or " ".join(_significant(entry.body))
        if kind == "malformed":
            errors.append(
                f"{label}: `{key}` is not valid YAML (line {entry.line_number}); "
                f"check for an unterminated quote or a stray `:`"
            )
        elif key in STRING_FIELDS:
            if kind == "null":
                errors.append(f"{label}: `{key}` is empty; it must be a string")
            elif kind != "str":
                errors.append(
                    f"{label}: `{key}` must be a string but YAML parses "
                    f"{shown!r} as {kind}; quote it"
                )
        elif key in BOOL_FIELDS and kind != "bool":
            errors.append(
                f"{label}: `{key}` must be a boolean but YAML parses "
                f"{shown!r} as {kind}"
            )

    for key in REQUIRED_FIELDS:
        if key not in parsed.entries:
            errors.append(f"{label}: missing `{key}`")


def discover(plugins_dir: Path) -> list[Path]:
    return sorted(plugins_dir.glob("*/commands/**/*.md"))


def validate_plugins(plugins_dir: Path) -> ValidationResult:
    errors: list[str] = []
    if not plugins_dir.is_dir():
        return ValidationResult(errors=[f"plugins dir not found: {plugins_dir}"])
    repo_root = plugins_dir.parent
    commands = discover(plugins_dir)
    for path in commands:
        try:
            label = str(path.relative_to(repo_root))
        except ValueError:
            label = str(path)
        validate_command(path, label, errors)
    return ValidationResult(errors=errors, command_count=len(commands))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "plugins_dir",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="path to the repository's plugins/ directory",
    )
    args = parser.parse_args(argv)
    result = validate_plugins(args.plugins_dir)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.errors:
        print(
            f"\nFAIL: {len(result.errors)} problem(s) across "
            f"{result.command_count} command file(s)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {result.command_count} commands, frontmatter valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
