#!/usr/bin/env python3
"""Validate the ``skills`` frontmatter of every subagent shipped by a plugin.

``skills`` preloads skill content into a subagent at startup. It sits directly
below ``tools``, which is a comma-separated *string*, and the two look
interchangeable. They are not, and getting it wrong fails asymmetrically:

  - Claude Code documents ``skills`` as a YAML list but tolerates a string, so
    an agent authored and tested there looks correct.
  - GitHub Copilot CLI validates it as an array and rejects the *entire*
    frontmatter on a type failure (``skills: Expected array, received
    string``). The agent then loads with empty metadata and never registers.

The damage is not a missing agent. Dispatching an unregistered agent fails with
"agent type isn't registered", and the caller's natural recovery is to
re-dispatch the same instructions to a general-purpose worker — silently
discarding the agent's ``tools`` restriction, so a read-only reviewer becomes a
worker that can write. That is why this is a gate and not a lint.

YAML parsing is reused from ``command_frontmatter``: this repo already resolves
frontmatter types there with the standard library (PyYAML is not a dependency),
and a second hand-rolled parser would drift from the first. Only the rules
specific to ``skills`` live here.

The existence check is deliberately monorepo-scoped: it asserts a named skill
exists somewhere under ``plugins/``, not that it ships in the agent's own
plugin. Cross-plugin preloads are legitimate — ``context-handoff``'s agent
preloads ``verify-before-trust`` from ``verify`` — but they are only safe
because the plugin declares that dependency, which this gate does not verify.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from command_frontmatter import Entry, entry_type, parse_frontmatter

FIELD = "skills"

ANCHOR_ONLY_RE = re.compile(r"^&\S+$")
QUOTES = ("'", '"')


@dataclass
class ValidationResult:
    errors: list[str]
    agent_count: int = 0
    skills_checked: int = 0
    known_skills: set[str] = field(default_factory=set)


def resolve_entry_type(entry: Entry) -> str:
    """Type of a ``skills`` entry, resolving an anchor-only inline value.

    ``command_frontmatter.resolve_type`` deliberately does not special-case
    ``&anchor``, because ``&a value`` resolves to the value it decorates. But
    ``skills: &a`` followed by an indented list is an *anchored sequence*, and
    treating the bare anchor as a scalar would reject valid YAML.
    """
    if ANCHOR_ONLY_RE.match(entry.inline.strip()):
        return entry_type(
            Entry(inline="", line_number=entry.line_number, body=entry.body)
        )
    return entry_type(entry)


def _split_flow(raw: str) -> list[str] | None:
    """Split a YAML flow sequence into its top-level items.

    Returns None when the sequence is unterminated. Nesting and quoting are
    tracked so ``[a, [b, c]]`` yields two items rather than three — the nested
    item is then rejected by the caller as a non-scalar.
    """
    if not raw.startswith("["):
        return None
    items: list[str] = []
    current = ""
    depth = 0
    quote: str | None = None
    for index, char in enumerate(raw):
        if quote is not None:
            current += char
            if char == quote and raw[index - 1 : index] != "\\":
                quote = None
            continue
        if char in QUOTES:
            quote = char
            current += char
            continue
        if char in "[{":
            depth += 1
            if depth == 1 and char == "[":
                continue
            current += char
            continue
        if char in "]}":
            depth -= 1
            if depth == 0 and char == "]":
                items.append(current)
                trailing = raw[index + 1 :].strip()
                if trailing and not trailing.startswith("#"):
                    return None
                return [
                    item.strip() for item in items if item.strip() or len(items) > 1
                ]
            current += char
            continue
        if char == "," and depth == 1:
            items.append(current)
            current = ""
            continue
        current += char
    return None


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES:
        return value[1:-1]
    return value


def sequence_items(entry: Entry) -> tuple[list[str], list[str]]:
    """Return (names, problems) for a ``skills`` entry already typed as a seq."""
    inline = entry.inline.strip()
    problems: list[str] = []
    raw_items: list[str] = []

    if inline.startswith("["):
        split = _split_flow(inline)
        if split is None:
            return [], ["flow sequence is unterminated or has trailing junk"]
        raw_items = split
    else:
        for line in entry.body:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "-" or not stripped.startswith("- "):
                if stripped.startswith("-"):
                    problems.append(f"list item {stripped!r} has no value")
                continue
            raw_items.append(stripped[2:].strip())

    names: list[str] = []
    for item in raw_items:
        if not item:
            problems.append("list contains an empty item")
            continue
        if item[:1] in ("[", "{", "-"):
            problems.append(
                f"list item {item!r} is not a plain string; `skills` must be a "
                f"flat array of skill names"
            )
            continue
        names.append(_unquote(item))
    return names, problems


def validate_agent(
    path: Path, label: str, known_skills: set[str], errors: list[str]
) -> bool:
    """Validate one agent's ``skills`` entry. Returns True if it declared one."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{label}: cannot read file: {exc}")
        return False

    parsed = parse_frontmatter(text)
    if parsed is None:
        # Absent or unterminated frontmatter is check-skills.sh's error to
        # report; duplicating it here would double every message.
        return False
    entry = parsed.entries.get(FIELD)
    if entry is None:
        return False

    kind = resolve_entry_type(entry)
    if kind == "seq":
        names, problems = sequence_items(entry)
        for problem in problems:
            errors.append(f"{label}:{entry.line_number}: `{FIELD}` {problem}")
        if not names and not problems:
            errors.append(
                f"{label}:{entry.line_number}: `{FIELD}` is declared but lists no skills"
            )
        for name in names:
            if name not in known_skills:
                errors.append(
                    f"{label}:{entry.line_number}: preloads unknown skill {name!r} "
                    f"(no plugins/*/skills/{name}/SKILL.md in this repo)"
                )
        return True

    if kind == "null":
        errors.append(
            f"{label}:{entry.line_number}: `{FIELD}` is declared but lists no skills"
        )
        return True

    suggestion = "\n".join(
        f"  - {part.strip()}"
        for part in _unquote(entry.inline).split(",")
        if part.strip()
    )
    errors.append(
        f"{label}:{entry.line_number}: `{FIELD}` must be a YAML list, not a "
        f"{kind}. GitHub Copilot validates it as an array and rejects the whole "
        f"frontmatter, so the agent never registers and callers silently fall "
        f"back to a general-purpose worker — dropping this agent's `tools` "
        f"restriction. Use:\n{FIELD}:\n{suggestion or '  - <skill-name>'}"
    )
    return True


def discover_agents(plugins_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in plugins_dir.glob("*/agents/**/*.md")
        if path.name != "README.md"
    )


def discover_skills(plugins_dir: Path) -> set[str]:
    return {path.parent.name for path in plugins_dir.glob("*/skills/*/SKILL.md")}


def validate_plugins(plugins_dir: Path) -> ValidationResult:
    errors: list[str] = []
    known = discover_skills(plugins_dir)
    agents = discover_agents(plugins_dir)
    checked = 0
    repo_dir = plugins_dir.parent
    for path in agents:
        try:
            label = str(path.relative_to(repo_dir))
        except ValueError:
            label = str(path)
        if validate_agent(path, label, known, errors):
            checked += 1
    return ValidationResult(
        errors=errors,
        agent_count=len(agents),
        skills_checked=checked,
        known_skills=known,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugins_dir", type=Path)
    args = parser.parse_args(argv)

    if not args.plugins_dir.is_dir():
        print(f"ERROR: plugins dir not found: {args.plugins_dir}", file=sys.stderr)
        return 2

    result = validate_plugins(args.plugins_dir.resolve())
    for message in result.errors:
        print(f"ERROR: {message}", file=sys.stderr)
    if result.errors:
        print(
            f"\nFAIL: {len(result.errors)} problem(s) across "
            f"{result.agent_count} agent(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: {result.agent_count} agents, "
        f"{result.skills_checked} with `skills` preloads, all valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
