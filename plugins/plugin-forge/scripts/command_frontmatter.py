#!/usr/bin/env python3
"""Validate the YAML frontmatter of every slash command shipped by a plugin.

Hosts reject a command whose frontmatter field parses to the wrong YAML type,
and the failure is fatal at load time rather than merely degraded: an unquoted
``argument-hint: [artifact-path]`` is a YAML *flow sequence*, not a string, so
the host refuses the command with ``argument-hint must be a string``.

Nothing else in this repo validates ``commands/*.md``. ``check-skills.sh`` only
covers skills and agents, and its line-oriented parser reads ``[x]`` as the
literal text ``"[x]"``, so it cannot see this class of breakage at all.

This gate resolves the YAML *type* each scalar would take, using only the
standard library (PyYAML is not a dependency of this repo), and fails when:

  - frontmatter is missing or never closed
  - a plain scalar contains ``": "``, which is a YAML parse error
  - a string-typed field would parse as a sequence, mapping, bool, number,
    null, timestamp, alias, or tag
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

# YAML 1.1 booleans; hosts and PyYAML both resolve the long and short spellings.
BOOL_LITERALS = frozenset(
    {"y", "n", "yes", "no", "true", "false", "on", "off"}
)
NULL_LITERALS = frozenset({"", "~", "null"})

INT_RE = re.compile(
    r"""^[-+]?(
        0b[01_]+
      | 0o?[0-7_]+
      | 0x[0-9a-fA-F_]+
      | [0-9][0-9_]*
    )$""",
    re.VERBOSE,
)
FLOAT_RE = re.compile(
    r"""^[-+]?(
        \.(inf|Inf|INF)
      | (?:[0-9][0-9_]*)?\.[0-9_]*(?:[eE][-+]?[0-9]+)?
      | [0-9][0-9_]*(?:[eE][-+]?[0-9]+)
    )$""",
    re.VERBOSE,
)
NAN_RE = re.compile(r"^\.(nan|NaN|NAN)$")
# Enough of the YAML timestamp resolver to catch a bare `2026-01-01`, which
# silently becomes a `datetime.date` rather than the string an author intended.
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}([Tt ].*)?$")


@dataclass
class Frontmatter:
    fields: dict[str, str]
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    errors: list[str]
    command_count: int = 0


def _strip_comment(value: str) -> str:
    """Drop a trailing YAML comment from a plain (unquoted) scalar."""
    index = value.find(" #")
    return value[:index].rstrip() if index != -1 else value


def _is_quoted(value: str) -> bool:
    return len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"')


def resolve_type(raw: str) -> str:
    """Return the YAML node type a frontmatter value resolves to.

    One of: ``str``, ``seq``, ``map``, ``bool``, ``int``, ``float``, ``null``,
    ``timestamp``, ``alias``, ``anchor``, or ``tag``.
    """
    value = raw.strip()
    if _is_quoted(value):
        return "str"
    if value[:1] in ("|", ">"):  # block scalar: the body follows, indented
        return "str"
    value = _strip_comment(value).strip()
    if value.startswith("["):
        return "seq"
    if value.startswith("{"):
        return "map"
    if value.startswith("*"):
        return "alias"
    if value.startswith("&"):
        return "anchor"
    if value.startswith("!"):
        return "tag"
    if _is_quoted(value):  # e.g. `"text"  # comment`
        return "str"
    if value.lower() in NULL_LITERALS:
        return "null"
    if value.lower() in BOOL_LITERALS:
        return "bool"
    if INT_RE.match(value):
        return "int"
    if FLOAT_RE.match(value) or NAN_RE.match(value):
        return "float"
    if TIMESTAMP_RE.match(value):
        return "timestamp"
    return "str"


def parse_frontmatter(text: str) -> Frontmatter | None:
    """Parse top-level frontmatter keys, or return ``None`` when absent/unclosed.

    Indented lines fold into the active key so block scalars and wrapped values
    parse. Nested mappings therefore collapse into their parent, which is fine:
    commands have no legitimate nested frontmatter, and a nested value under a
    string-typed key is reported through the empty-value path.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None
    parsed = Frontmatter(fields={})
    active: str | None = None
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == FENCE:
            return parsed
        if not line.strip():
            continue
        if line[0] in (" ", "\t"):
            if active is not None:
                parsed.fields[active] = (
                    parsed.fields[active] + " " + line.strip()
                ).strip()
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
        if key in parsed.fields:
            parsed.errors.append(f"line {number}: duplicate key `{key}`")
        value = rest.strip()
        if not _is_quoted(value) and value[:1] not in ("|", ">", "[", "{"):
            plain = _strip_comment(value)
            if ": " in plain or plain.endswith(":"):
                parsed.errors.append(
                    f"line {number}: `{key}` value contains an unquoted `:` "
                    f"and is a YAML parse error; quote it"
                )
        active = key
        parsed.fields[key] = value
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

    for key, raw in parsed.fields.items():
        if key not in KNOWN_FIELDS:
            errors.append(
                f"{label}: unknown frontmatter key `{key}` "
                f"(known: {', '.join(sorted(KNOWN_FIELDS))})"
            )
            continue
        kind = resolve_type(raw)
        if key in STRING_FIELDS:
            if kind == "null":
                errors.append(f"{label}: `{key}` is empty; it must be a string")
            elif kind != "str":
                errors.append(
                    f"{label}: `{key}` must be a string but YAML parses "
                    f"{raw!r} as {kind}; quote it"
                )
        elif key in BOOL_FIELDS and kind != "bool":
            errors.append(
                f"{label}: `{key}` must be a boolean but YAML parses "
                f"{raw!r} as {kind}"
            )

    for key in REQUIRED_FIELDS:
        if not parsed.fields.get(key, "").strip():
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
