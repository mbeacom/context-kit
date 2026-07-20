#!/usr/bin/env python3
"""Validate durable memories and invoke an optional MemPalace provider."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = "context-kit/memory-v1"
MAX_BYTES = 32 * 1024
MAX_MEMORY_LINES = 220
MAX_HANDOFF_LINES = 300
MAX_HANDOFF_ITEMS = 25
MAX_CUES = 3
PROJECT_SLUG_PREFIX_LENGTH = 31
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]+\}\}")
LIST_ITEM_RE = re.compile(r"^(?:[-*+] |\d+[.)] )")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
MEMORY_TYPES = {"fact", "decision", "procedure", "constraint", "episode"}
SCOPES = {"project"}
FRESHNESS_STATES = {"current", "stale", "superseded", "revoked"}
REVIEW_STATES = {"proposed", "accepted", "rejected"}
STATE_SCHEMA = "context-kit/memory-state-v1"
RECEIPT_SCHEMA = "context-kit/memory-provider-receipt-v1"
REVIEW_TRANSITIONS = {
    "proposed": {"accepted", "rejected"},
    "accepted": {"rejected"},
    "rejected": {"accepted"},
}
FRESHNESS_TRANSITIONS = {
    "current": {"stale", "superseded", "revoked"},
    "stale": {"current", "superseded", "revoked"},
    "superseded": set(),
    "revoked": set(),
}
REQUIRED_FIELDS = (
    "schema",
    "id",
    "type",
    "scope",
    "repository",
    "branch",
    "head",
    "observed_at",
    "captured_at",
    "freshness",
    "review",
    "source",
    "source_hash",
)
MEMORY_HEADINGS = (
    "## Primary Memory",
    "## Cue Anchors",
    "## Evidence",
    "## Supersedes",
    "## Review Notes",
)
HANDOFF_FIELDS = (
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
HANDOFF_HEADINGS = (
    "## Scope",
    "## Verified Facts",
    "## Decisions",
    "## Changed Files",
    "## Completed Work",
    "## Unresolved Items",
    "## Next Steps",
    "## Validation State",
    "## Provenance and Freshness",
)


class Refusal(ValueError):
    """An invalid input or unsafe provider request."""


@dataclass(frozen=True)
class Config:
    provider: str
    home: Path
    project: str | None
    auto_capture: bool

    @property
    def project_slug(self) -> str:
        if not self.project:
            raise Refusal(
                "set CONTEXT_KIT_MEMORY_PROJECT (or pass --project) to isolate memory"
            )
        if not REPOSITORY_RE.fullmatch(self.project):
            raise Refusal("memory project must be a concrete owner/name identity")
        prefix = re.sub(r"[^A-Za-z0-9._-]+", "-", self.project).strip("-").lower()
        digest = hashlib.sha256(self.project.encode("utf-8")).hexdigest()
        return f"{prefix[:PROJECT_SLUG_PREFIX_LENGTH]}-{digest}"

    @property
    def palace_path(self) -> Path:
        return self.home / "providers" / "mempalace" / self.project_slug / "palace"

    @property
    def records_path(self) -> Path:
        return self.home / "records" / self.project_slug

    @property
    def states_path(self) -> Path:
        return self.home / "states" / self.project_slug

    @property
    def receipts_path(self) -> Path:
        return self.home / "receipts" / self.project_slug


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _config(args: argparse.Namespace) -> Config:
    provider = (
        getattr(args, "provider", None)
        or _first_env(
            "CONTEXT_KIT_MEMORY_PROVIDER",
            "CLAUDE_PLUGIN_OPTION_PROVIDER",
        )
        or "none"
    ).lower()
    if provider not in {"none", "mempalace"}:
        raise Refusal("memory provider must be 'none' or 'mempalace'")

    home_value = (
        getattr(args, "home", None)
        or _first_env(
            "CONTEXT_KIT_MEMORY_HOME",
            "CLAUDE_PLUGIN_OPTION_MEMORY_HOME",
        )
        or "~/.local/share/context-kit/memory"
    )
    home = Path(home_value).expanduser().resolve()
    project = getattr(args, "project", None) or _first_env(
        "CONTEXT_KIT_MEMORY_PROJECT",
        "CLAUDE_PLUGIN_OPTION_PROJECT",
    )
    auto_value = _first_env(
        "CONTEXT_KIT_MEMORY_AUTO_CAPTURE",
        "CLAUDE_PLUGIN_OPTION_AUTO_CAPTURE",
    )
    return Config(
        provider=provider,
        home=home,
        project=project,
        auto_capture=_truthy(auto_value),
    )


def _parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise Refusal("artifact must start with flat YAML frontmatter")
    fields: dict[str, str] = {}
    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break
        if not line or line[0].isspace() or ":" not in line:
            raise Refusal(
                "frontmatter must contain only flat non-empty key/value fields"
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not key or not value or key in fields:
            raise Refusal("frontmatter contains an empty or duplicate field")
        fields[key] = value
    if closing is None:
        raise Refusal("frontmatter is missing its closing delimiter")
    return fields, lines[closing + 1 :]


def _validate_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Refusal(f"{field} must include a timezone")


def _build_sections(
    body: list[str],
    headings: tuple[str, ...],
    found: list[tuple[str, int]],
) -> dict[str, list[str]]:
    found_headings = [heading for heading, _position in found]
    if found_headings != list(headings):
        raise Refusal("artifact headings are missing, reordered, or unexpected")
    positions = [position for _heading, position in found]
    result: dict[str, list[str]] = {}
    for index, heading in enumerate(headings):
        end = positions[index + 1] if index + 1 < len(positions) else len(body)
        result[heading] = body[positions[index] + 1 : end]
    return result


def _memory_sections(body: list[str]) -> dict[str, list[str]]:
    found: list[tuple[str, int]] = []
    fence: tuple[str, int] | None = None
    for index, line in enumerate(body):
        fence_match = FENCE_RE.match(line)
        if fence is not None:
            if fence_match:
                marker, suffix = fence_match.groups()
                if (
                    marker[0] == fence[0]
                    and len(marker) >= fence[1]
                    and not suffix.strip()
                ):
                    fence = None
            continue
        if fence_match:
            marker, _suffix = fence_match.groups()
            fence = (marker[0], len(marker))
            continue
        if line.startswith("## "):
            found.append((line, index))
    return _build_sections(body, MEMORY_HEADINGS, found)


def _handoff_sections(body: list[str]) -> dict[str, list[str]]:
    found = []
    for index, line in enumerate(body):
        if line.startswith("## "):
            found.append((f"## {line[3:].strip()}", index))
    return _build_sections(body, HANDOFF_HEADINGS, found)


def _nonempty_section(lines: list[str], heading: str) -> str:
    text = "\n".join(lines).strip()
    if not text or text == "- None.":
        raise Refusal(f"{heading} must not be empty")
    return text


def _required_section(lines: list[str], heading: str) -> str:
    text = "\n".join(lines).strip()
    if not text:
        raise Refusal(f"{heading} must not be empty; use '- None.'")
    return text


def _validate_branch(value: str) -> None:
    try:
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", value],
            capture_output=True,
            check=False,
            text=True,
            timeout=5.0,
        )
    except FileNotFoundError as exc:
        raise Refusal("git is required to validate branch provenance") from exc
    except subprocess.TimeoutExpired as exc:
        raise Refusal("Git branch validation timed out") from exc
    if result.returncode != 0:
        raise Refusal("branch must be a valid concrete Git branch name")


def _read_bounded(
    path: Path, *, max_lines: int = MAX_MEMORY_LINES
) -> tuple[bytes, str]:
    if not path.is_file():
        raise Refusal(f"artifact is not a file: {path}")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise Refusal(f"artifact exceeds {MAX_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("artifact must be UTF-8") from exc
    if len(text.splitlines()) > max_lines:
        raise Refusal(f"artifact exceeds {max_lines} lines")
    return raw, text


def validate_memory(path: Path, *, verify_source: bool = True) -> dict[str, object]:
    raw, text = _read_bounded(path)
    fields, body = _parse_frontmatter(text)
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    extras = sorted(set(fields) - set(REQUIRED_FIELDS))
    if missing or extras:
        raise Refusal(
            f"memory frontmatter mismatch; missing={missing or 'none'} "
            f"unexpected={extras or 'none'}"
        )
    if fields["schema"] != SCHEMA:
        raise Refusal(f"schema must be {SCHEMA}")
    if not ID_RE.fullmatch(fields["id"]):
        raise Refusal("memory id must be lowercase and use letters, numbers, ._-")
    if fields["type"] not in MEMORY_TYPES:
        raise Refusal(f"memory type must be one of {sorted(MEMORY_TYPES)}")
    if fields["scope"] not in SCOPES:
        raise Refusal("memory scope must be 'project'")
    if fields["freshness"] not in FRESHNESS_STATES:
        raise Refusal(f"freshness must be one of {sorted(FRESHNESS_STATES)}")
    if fields["review"] not in REVIEW_STATES:
        raise Refusal(f"review must be one of {sorted(REVIEW_STATES)}")
    if not HASH_RE.fullmatch(fields["source_hash"]):
        raise Refusal("source_hash must be a lowercase SHA-256 digest")
    _validate_timestamp(fields["observed_at"], "observed_at")
    _validate_timestamp(fields["captured_at"], "captured_at")
    if not REPOSITORY_RE.fullmatch(fields["repository"]):
        raise Refusal("repository must be a concrete owner/name identity")
    _validate_branch(fields["branch"])
    if not COMMIT_RE.fullmatch(fields["head"]):
        raise Refusal("head must be a 7-64 character hexadecimal commit")

    sections = _memory_sections(body)
    primary = _nonempty_section(sections["## Primary Memory"], "Primary Memory")
    if len(primary) > 600:
        raise Refusal("Primary Memory must be at most 600 characters")
    _nonempty_section(sections["## Evidence"], "Evidence")

    cue_lines = [line.strip() for line in sections["## Cue Anchors"] if line.strip()]
    if cue_lines == ["- None."]:
        cues: list[str] = []
    else:
        if not cue_lines or any(
            not line.startswith("- ") or line == "- None." for line in cue_lines
        ):
            raise Refusal("Cue Anchors must contain only bullets or '- None.'")
        cues = [line[2:].strip() for line in cue_lines]
    if len(cues) > MAX_CUES:
        raise Refusal(f"Cue Anchors may contain at most {MAX_CUES} entries")
    if any(not cue or len(cue) > 120 for cue in cues):
        raise Refusal("each cue anchor must contain 1..120 characters")
    _required_section(sections["## Supersedes"], "Supersedes")
    _nonempty_section(sections["## Review Notes"], "Review Notes")

    source = Path(fields["source"]).expanduser()
    if verify_source and source.is_file():
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != fields["source_hash"]:
            raise Refusal("source_hash does not match the referenced source file")
    return {
        **fields,
        "artifact_hash": hashlib.sha256(raw).hexdigest(),
        "primary_memory": primary,
        "cue_anchors": cues,
    }


def validate_handoff(path: Path) -> dict[str, object]:
    raw, text = _read_bounded(path, max_lines=MAX_HANDOFF_LINES)
    if PLACEHOLDER_RE.search(text):
        raise Refusal("handoff contains unresolved {{...}} template placeholders")
    fields, body = _parse_frontmatter(text)
    missing = [field for field in HANDOFF_FIELDS if field not in fields]
    if missing:
        raise Refusal(f"handoff is missing required fields: {', '.join(missing)}")
    if fields["schema"] != "context-kit/handoff-v1":
        raise Refusal("handoff schema must be context-kit/handoff-v1")
    _validate_timestamp(fields["generated_at"], "generated_at")
    for field in ("head", "base_commit"):
        if not COMMIT_RE.fullmatch(fields[field]):
            raise Refusal(f"{field} must be a 7-64 character hexadecimal commit")
    if fields["worktree_state"] not in {"clean", "dirty"}:
        raise Refusal("handoff worktree_state must be clean or dirty")
    titles = [line.strip() for line in body if line.startswith("# ")]
    if titles != ["# Context Handoff"]:
        raise Refusal("handoff must contain exactly one '# Context Handoff' title")
    sections = _handoff_sections(body)
    for heading, lines in sections.items():
        _required_section(lines, heading.removeprefix("## "))
        item_count = sum(
            bool(LIST_ITEM_RE.match(line)) for line in lines if line.strip()
        )
        if item_count > MAX_HANDOFF_ITEMS:
            raise Refusal(
                f"{heading.removeprefix('## ')} has {item_count} list items; "
                f"maximum is {MAX_HANDOFF_ITEMS}"
            )
    return {**fields, "artifact_hash": hashlib.sha256(raw).hexdigest()}


def _git(repo: Path, *argv: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *argv],
            capture_output=True,
            check=False,
            text=True,
            timeout=20.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise Refusal("git context check timed out") from exc
    if result.returncode != 0:
        error = result.stderr.strip()
        raise Refusal(f"cannot establish repository context: {error or 'git failed'}")
    return result.stdout.strip()


def _normalize_repository(remote: str) -> str:
    value = remote.strip()
    if value.startswith("git@") and ":" in value:
        value = value.split(":", 1)[1]
    elif "://" in value:
        value = value.split("://", 1)[1]
        if "@" in value.split("/", 1)[0]:
            value = value.split("@", 1)[1]
        value = value.split("/", 1)[1] if "/" in value else value
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    parts = [part for part in value.split("/") if part]
    if len(parts) < 2:
        raise Refusal("cannot normalize the repository remote to owner/name")
    return "/".join(parts[-2:])


def _assert_project_matches(metadata: dict[str, object], config: Config) -> None:
    project = config.project
    if not project:
        config.project_slug
    if metadata["repository"] != project:
        raise Refusal(
            "artifact repository does not match configured memory project: "
            f"artifact={metadata['repository']!r} project={project!r}"
        )


def _assert_handoff_current(metadata: dict[str, object], repo: Path) -> None:
    root = Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()
    remote = _normalize_repository(_git(root, "remote", "get-url", "origin"))
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    base_commit = _git(root, "merge-base", "HEAD", metadata["base_ref"])
    worktree_state = "dirty" if _git(root, "status", "--porcelain") else "clean"
    checks = {
        "repository": remote,
        "branch": branch,
        "head": head,
        "base_commit": base_commit,
        "worktree_state": worktree_state,
    }
    differences = [
        f"{field}: saved={metadata[field]!r} current={current!r}"
        for field, current in checks.items()
        if metadata[field] != current
    ]
    if differences:
        raise Refusal(
            "handoff is mismatched or stale; validate/resume it before archival: "
            + "; ".join(differences)
        )


def _write_once(destination: Path, raw: bytes) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        handle.write(raw)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    try:
        os.link(temporary, destination)
    except FileExistsError:
        if destination.read_bytes() == raw:
            return "unchanged"
        raise Refusal(f"refusing to overwrite a different artifact: {destination}")
    finally:
        temporary.unlink(missing_ok=True)
    return "created"


def _utc_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _new_write_once_path(directory: Path, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = _utc_timestamp().replace("-", "").replace(":", "").replace("+", "p")
    return directory / f"{stamp}-{os.getpid()}-{uuid.uuid4().hex}{suffix}"


def _write_json_once(directory: Path, payload: dict[str, object]) -> Path:
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    destination = _new_write_once_path(directory, ".json")
    if _write_once(destination, raw) != "created":
        raise Refusal(f"refusing to reuse a generated write-once path: {destination}")
    return destination


def _initial_state(metadata: dict[str, object]) -> dict[str, str]:
    return {
        "review": str(metadata["review"]),
        "freshness": str(metadata["freshness"]),
    }


def _event_paths(config: Config, record_id: str) -> list[Path]:
    directory = config.states_path / record_id
    return sorted(directory.glob("*.json")) if directory.exists() else []


@contextlib.contextmanager
def _state_lock(config: Config, record_id: str):
    """Serialize state transitions without making the evidence artifact writable."""
    parent = config.states_path / record_id
    parent.mkdir(parents=True, exist_ok=True)
    lock = parent / ".lock"
    deadline = time.monotonic() + 5.0
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise Refusal(f"state transition is busy for record: {record_id}")
            time.sleep(0.02)
    try:
        yield
    finally:
        lock.rmdir()


def _validate_state_event(
    path: Path,
    *,
    metadata: dict[str, object],
    config: Config,
    state: dict[str, str],
) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"invalid state event {path}: {exc}") from exc
    required = {
        "schema",
        "event_id",
        "record_id",
        "record_hash",
        "project",
        "project_key",
        "timestamp",
        "prior_review",
        "prior_freshness",
        "effective_review",
        "effective_freshness",
        "reason",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise Refusal(f"state event has an invalid schema: {path}")
    if payload["schema"] != STATE_SCHEMA:
        raise Refusal(f"state event has an unsupported schema: {path}")
    if (
        payload["record_id"] != metadata["id"]
        or payload["record_hash"] != metadata["artifact_hash"]
    ):
        raise Refusal(f"state event does not bind the exact record: {path}")
    if (
        payload["project"] != config.project
        or payload["project_key"] != config.project_slug
    ):
        raise Refusal(f"state event belongs to another project: {path}")
    if not isinstance(payload["event_id"], str) or not payload["event_id"]:
        raise Refusal(f"state event is missing an event_id: {path}")
    if not isinstance(payload["reason"], str) or not payload["reason"].strip():
        raise Refusal(f"state event is missing a reason: {path}")
    if len(payload["reason"]) > 1000:
        raise Refusal(f"state event reason is too long: {path}")
    for key in ("timestamp",):
        if not isinstance(payload[key], str):
            raise Refusal(f"state event has a non-string {key}: {path}")
        _validate_timestamp(payload[key], key)
    for key, allowed in (
        ("prior_review", REVIEW_STATES),
        ("effective_review", REVIEW_STATES),
        ("prior_freshness", FRESHNESS_STATES),
        ("effective_freshness", FRESHNESS_STATES),
    ):
        if not isinstance(payload[key], str) or payload[key] not in allowed:
            raise Refusal(f"state event has invalid {key}: {path}")
    if (
        payload["prior_review"] != state["review"]
        or payload["prior_freshness"] != state["freshness"]
    ):
        raise Refusal(f"state event prior state does not match its history: {path}")
    _validate_transition(
        state,
        {
            "review": str(payload["effective_review"]),
            "freshness": str(payload["effective_freshness"]),
        },
    )
    return payload


def _validate_transition(previous: dict[str, str], next_state: dict[str, str]) -> None:
    if previous == next_state:
        raise Refusal("state event must change review or freshness")
    if (
        previous["review"] != next_state["review"]
        and next_state["review"] not in REVIEW_TRANSITIONS[previous["review"]]
    ):
        raise Refusal(
            f"invalid review transition: {previous['review']} -> {next_state['review']}"
        )
    if (
        previous["freshness"] != next_state["freshness"]
        and next_state["freshness"] not in FRESHNESS_TRANSITIONS[previous["freshness"]]
    ):
        raise Refusal(
            "invalid freshness transition: "
            f"{previous['freshness']} -> {next_state['freshness']}"
        )


def effective_state(metadata: dict[str, object], config: Config) -> dict[str, str]:
    """Resolve immutable initial frontmatter plus append-only state events."""
    state = _initial_state(metadata)
    for path in _event_paths(config, str(metadata["id"])):
        event = _validate_state_event(
            path, metadata=metadata, config=config, state=state
        )
        state = {
            "review": str(event["effective_review"]),
            "freshness": str(event["effective_freshness"]),
        }
    return state


def _load_record(
    path: Path, config: Config
) -> tuple[dict[str, object], dict[str, str]]:
    metadata = validate_memory(path, verify_source=False)
    _assert_project_matches(metadata, config)
    return metadata, effective_state(metadata, config)


def _is_active(state: dict[str, str]) -> bool:
    return state == {"review": "accepted", "freshness": "current"}


def _source_state(metadata: dict[str, object]) -> str:
    source = Path(str(metadata["source"])).expanduser()
    if not source.is_file():
        return "unavailable"
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    return "verified" if actual == metadata["source_hash"] else "drifted"


def _active_projection(
    config: Config,
) -> tuple[list[tuple[Path, dict[str, object]]], list[dict[str, str]]]:
    included: list[tuple[Path, dict[str, object]]] = []
    excluded: list[dict[str, str]] = []
    for path in (
        sorted(config.records_path.glob("*.md")) if config.records_path.exists() else []
    ):
        try:
            metadata, state = _load_record(path, config)
            if _is_active(state):
                included.append((path, metadata))
            else:
                excluded.append(
                    {
                        "id": str(metadata["id"]),
                        "review": state["review"],
                        "freshness": state["freshness"],
                    }
                )
        except Refusal as exc:
            excluded.append({"artifact": str(path), "error": str(exc)})
    return included, excluded


def _projection_hash(records: list[tuple[Path, dict[str, object]]]) -> str:
    digest = hashlib.sha256()
    for _, metadata in records:
        digest.update(str(metadata["id"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(metadata["artifact_hash"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _materialize_projection(
    records: list[tuple[Path, dict[str, object]]], destination: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise Refusal(
            f"refusing to reuse a non-empty projection directory: {destination}"
        )
    for path, metadata in records:
        target = destination / f"{metadata['id']}.md"
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)


def _provider_receipt(
    config: Config,
    *,
    provider_version: str,
    operation: str,
    artifact_hash: str | None,
    argv: list[str],
    outcome: str,
    detail: str,
    projection_hash: str | None = None,
    backup_path: Path | None = None,
) -> Path:
    payload: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": uuid.uuid4().hex,
        "timestamp": _utc_timestamp(),
        "provider": "mempalace",
        "provider_version": provider_version,
        "project": config.project,
        "project_key": config.project_slug,
        "palace_path": str(config.palace_path),
        "operation": operation,
        "artifact_hash": artifact_hash,
        "projection_hash": projection_hash,
        "argv": argv,
        "outcome": outcome,
        "detail": detail,
        "backup_path": str(backup_path) if backup_path else None,
    }
    return _write_json_once(config.receipts_path, payload)


def _mempalace_executable() -> str:
    override = _first_env("CONTEXT_KIT_MEMPALACE_BIN")
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_absolute():
            raise Refusal("CONTEXT_KIT_MEMPALACE_BIN must be an absolute path")
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise Refusal(
                f"configured MemPalace executable is not runnable: {candidate}"
            )
        return str(candidate)
    executable = shutil.which("mempalace")
    if not executable:
        raise Refusal(
            "MemPalace provider selected but `mempalace` is not installed; "
            "install it separately with `uv tool install mempalace`"
        )
    return executable


def _provider_env(config: Config, palace_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    path = palace_path or config.palace_path
    path.parent.mkdir(parents=True, exist_ok=True)
    env["MEMPALACE_PALACE_PATH"] = str(path)
    return env


def _run_mempalace(
    config: Config,
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: float = 120.0,
    palace_path: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if config.provider != "mempalace":
        raise Refusal("this operation requires CONTEXT_KIT_MEMORY_PROVIDER=mempalace")
    executable = _mempalace_executable()
    try:
        result = subprocess.run(
            [executable, *argv],
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=_provider_env(config, palace_path),
        )
    except subprocess.TimeoutExpired as exc:
        raise Refusal(f"MemPalace command timed out after {timeout:g}s") from exc
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise Refusal(
            f"MemPalace exited {result.returncode}: {error or 'no error output'}"
        )
    return result


def _write_stdout(raw: bytes) -> None:
    sys.stdout.write(raw.decode("utf-8", errors="replace"))


def _mempalace_version(config: Config) -> tuple[str, str]:
    executable = _mempalace_executable()
    version = _run_mempalace(config, ["--version"], timeout=20.0)
    return executable, version.stdout.decode("utf-8", errors="replace").strip()


def _archive_active_projection(
    config: Config, *, operation: str, artifact_hash: str | None
) -> tuple[bool, str, Path | None]:
    records, _ = _active_projection(config)
    projection_hash = _projection_hash(records)
    if not records:
        receipt = _provider_receipt(
            config,
            provider_version="not-invoked",
            operation=operation,
            artifact_hash=artifact_hash,
            argv=[],
            outcome="skipped",
            detail="no accepted/current records are eligible for provider archival",
            projection_hash=projection_hash,
        )
        return (
            False,
            "no accepted/current records are eligible for provider archival",
            receipt,
        )

    projection_parent = config.home / "providers" / "mempalace" / config.project_slug
    projection_parent.mkdir(parents=True, exist_ok=True)
    projection = Path(tempfile.mkdtemp(prefix=".projection-", dir=projection_parent))
    executable = ""
    argv: list[str] = []
    try:
        _materialize_projection(records, projection)
        executable, version = _mempalace_version(config)
        argv = [executable, "mine", str(projection), "--wing", config.project_slug]
        _run_mempalace(
            config,
            argv[1:],
            timeout=300.0,
        )
    except Refusal as exc:
        receipt = _provider_receipt(
            config,
            provider_version="unknown",
            operation=operation,
            artifact_hash=artifact_hash,
            argv=argv,
            outcome="failed",
            detail=str(exc),
            projection_hash=projection_hash,
        )
        raise Refusal(f"{exc}; receipt={receipt}") from exc
    finally:
        shutil.rmtree(projection, ignore_errors=True)
    receipt = _provider_receipt(
        config,
        provider_version=version,
        operation=operation,
        artifact_hash=artifact_hash,
        argv=argv,
        outcome="success",
        detail=f"indexed {len(records)} accepted/current records",
        projection_hash=projection_hash,
    )
    return True, "archived accepted/current projection", receipt


def _capture_memory(args: argparse.Namespace, config: Config) -> int:
    source = Path(args.artifact).expanduser().resolve()
    metadata = validate_memory(source)
    _assert_project_matches(metadata, config)
    raw = source.read_bytes()
    destination = config.records_path / f"{metadata['id']}.md"
    state = _write_once(destination, raw)
    archived = False
    archive_reason = "provider not selected"
    receipt: Path | None = None
    effective = effective_state(metadata, config)
    if config.provider == "mempalace" and not args.local_only:
        if _is_active(effective):
            archived, archive_reason, receipt = _archive_active_projection(
                config,
                operation="capture",
                artifact_hash=str(metadata["artifact_hash"]),
            )
        else:
            archive_reason = (
                "skipped: record is not eligible for provider archival "
                f"(review={effective['review']}, freshness={effective['freshness']})"
            )
            receipt = _provider_receipt(
                config,
                provider_version="not-invoked",
                operation="capture",
                artifact_hash=str(metadata["artifact_hash"]),
                argv=[],
                outcome="skipped",
                detail=archive_reason,
            )
    elif args.local_only:
        archive_reason = "skipped: --local-only"
    print(
        json.dumps(
            {
                "status": state,
                "artifact": str(destination),
                "project": config.project_slug,
                "provider": config.provider,
                "provider_archived": archived,
                "provider_archive": {
                    "outcome": "success" if archived else "skipped",
                    "reason": archive_reason,
                    "receipt": str(receipt) if receipt else None,
                },
                "effective_state": effective,
            }
        )
    )
    return 0


def _archive_handoff(args: argparse.Namespace, config: Config) -> int:
    source = Path(args.artifact).expanduser().resolve()
    metadata = validate_handoff(source)
    _assert_project_matches(metadata, config)
    _assert_handoff_current(metadata, Path(args.repo).expanduser().resolve())
    raw = source.read_bytes()
    name = (
        f"handoff-{metadata['generated_at'][:10]}-{metadata['artifact_hash'][:12]}.md"
    )
    destination = config.home / "handoffs" / config.project_slug / name
    state = _write_once(destination, raw)
    archived = False
    archive_reason = "provider not selected"
    receipt: Path | None = None
    if config.provider == "mempalace" and not args.local_only:
        archive_reason = (
            "skipped: handoffs are local historical evidence, not active memory"
        )
        receipt = _provider_receipt(
            config,
            provider_version="not-invoked",
            operation="archive-handoff",
            artifact_hash=str(metadata["artifact_hash"]),
            argv=[],
            outcome="skipped",
            detail=archive_reason,
        )
    elif args.local_only:
        archive_reason = "skipped: --local-only"
    print(
        json.dumps(
            {
                "status": state,
                "artifact": str(destination),
                "project": config.project_slug,
                "provider": config.provider,
                "provider_archived": archived,
                "provider_archive": {
                    "outcome": "skipped",
                    "reason": archive_reason,
                    "receipt": str(receipt) if receipt else None,
                },
                "saved_head": metadata["head"],
            }
        )
    )
    return 0


def _local_search(args: argparse.Namespace, config: Config) -> int:
    terms = {term.lower() for term in TOKEN_RE.findall(args.query)}
    if not terms:
        raise Refusal("search query must contain at least one searchable term")
    results: list[dict[str, object]] = []
    invalid_records: list[dict[str, str]] = []
    inactive_records: list[dict[str, str]] = []
    for path in (
        sorted(config.records_path.glob("*.md")) if config.records_path.exists() else []
    ):
        try:
            metadata, state = _load_record(path, config)
        except Refusal as exc:
            invalid_records.append({"artifact": str(path), "error": str(exc)})
            continue
        if not _is_active(state) and not args.include_inactive:
            inactive_records.append(
                {
                    "id": str(metadata["id"]),
                    "review": state["review"],
                    "freshness": state["freshness"],
                }
            )
            continue
        primary = metadata["primary_memory"]
        cues = metadata["cue_anchors"]
        primary_text = primary.lower()
        cue_text = " ".join(cues).lower()
        source_state = _source_state(metadata)
        primary_matches = sum(term in primary_text for term in terms)
        cue_matches = sum(term in cue_text for term in terms)
        score = primary_matches * 2 + cue_matches
        if score:
            results.append(
                {
                    "id": metadata["id"],
                    "type": metadata["type"],
                    "freshness": state["freshness"],
                    "review": state["review"],
                    "primary_memory": primary,
                    "cue_anchors": cues,
                    "source": metadata["source"],
                    "source_hash": metadata["source_hash"],
                    "source_state": source_state,
                    "score": score,
                }
            )
    results.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
    print(
        json.dumps(
            {
                "provider": "local",
                "project": config.project_slug,
                "records": results[: args.results],
                "invalid_records": invalid_records,
                "inactive_records": inactive_records,
                "include_inactive": args.include_inactive,
            }
        )
    )
    return 0


def _search(args: argparse.Namespace, config: Config) -> int:
    if config.provider == "none":
        return _local_search(args, config)
    if args.include_inactive:
        raise Refusal(
            "--include-inactive is available only for local audit search; "
            "the provider index is active-only"
        )
    records, _ = _active_projection(config)
    projection_hash = _projection_hash(records)
    if not _has_current_provider_projection(config, projection_hash):
        raise Refusal(
            "provider index is not reconciled with accepted/current records; "
            "run sync-provider --apply or use --provider none for local recall"
        )
    result = _run_mempalace(
        config,
        ["search", args.query, "--results", str(args.results)],
    )
    _write_stdout(result.stdout)
    return 0


def _wake(config: Config) -> int:
    config.project_slug
    result = _run_mempalace(config, ["wake-up"])
    _write_stdout(result.stdout)
    return 0


def _doctor(config: Config) -> int:
    result: dict[str, object] = {
        "provider": config.provider,
        "home": str(config.home),
        "project": config.project,
        "auto_capture": config.auto_capture,
    }
    if config.provider == "none":
        result.update(
            {
                "status": "ready",
                "mode": "local",
                "records_path": str(config.home / "records" / config.project_slug),
            }
        )
        print(json.dumps(result))
        return 0
    config.project_slug
    executable = _mempalace_executable()
    version = _run_mempalace(config, ["--version"], timeout=20.0)
    result.update(
        {
            "status": "ready",
            "executable": executable,
            "palace_path": str(config.palace_path),
            "version": version.stdout.decode("utf-8", errors="replace").strip(),
        }
    )
    print(json.dumps(result))
    return 0


def _record_review(config: Config) -> int:
    results: list[dict[str, str]] = []
    for path in (
        sorted(config.records_path.glob("*.md")) if config.records_path.exists() else []
    ):
        try:
            metadata, state = _load_record(path, config)
            results.append(
                {
                    "id": metadata["id"],
                    "artifact": str(path),
                    "freshness": state["freshness"],
                    "review": state["review"],
                    "source_state": _source_state(metadata),
                    "active": str(_is_active(state)).lower(),
                }
            )
        except Refusal as exc:
            results.append(
                {
                    "artifact": str(path),
                    "source_state": "invalid-or-stale",
                    "error": str(exc),
                }
            )
    print(
        json.dumps(
            {
                "project": config.project_slug,
                "records": results,
                "audit": True,
                "include_inactive": True,
            }
        )
    )
    return 0


def _record_state(args: argparse.Namespace, config: Config) -> int:
    if not ID_RE.fullmatch(args.record_id):
        raise Refusal("record id must be lowercase and use letters, numbers, ._-")
    path = config.records_path / f"{args.record_id}.md"
    if not path.is_file():
        raise Refusal(f"record does not exist in this project: {args.record_id}")
    reason = args.reason.strip()
    if not reason:
        raise Refusal("--reason must not be empty")
    with _state_lock(config, args.record_id):
        metadata, current = _load_record(path, config)
        requested = {
            "review": args.review if args.review is not None else current["review"],
            "freshness": (
                args.freshness if args.freshness is not None else current["freshness"]
            ),
        }
        _validate_transition(current, requested)
        payload: dict[str, object] = {
            "schema": STATE_SCHEMA,
            "event_id": uuid.uuid4().hex,
            "record_id": metadata["id"],
            "record_hash": metadata["artifact_hash"],
            "project": config.project,
            "project_key": config.project_slug,
            "timestamp": _utc_timestamp(),
            "prior_review": current["review"],
            "prior_freshness": current["freshness"],
            "effective_review": requested["review"],
            "effective_freshness": requested["freshness"],
            "reason": reason,
        }
        event = _write_json_once(config.states_path / args.record_id, payload)
    print(
        json.dumps(
            {
                "status": "created",
                "event": str(event),
                "record": str(path),
                "record_hash": metadata["artifact_hash"],
                "project": config.project_slug,
                "prior_state": current,
                "effective_state": requested,
                "provider_reconciliation": (
                    "required before provider recall"
                    if config.provider == "mempalace"
                    else "not-applicable"
                ),
            }
        )
    )
    return 0


def _read_receipts(config: Config) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    if not config.receipts_path.exists():
        return receipts
    for path in sorted(config.receipts_path.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("schema") == RECEIPT_SCHEMA
            and payload.get("project") == config.project
            and payload.get("project_key") == config.project_slug
        ):
            receipts.append(payload)
    return receipts


def _has_current_provider_projection(config: Config, projection_hash: str) -> bool:
    return any(
        receipt.get("outcome") == "success"
        and receipt.get("operation") == "sync-provider"
        and receipt.get("projection_hash") == projection_hash
        for receipt in _read_receipts(config)
    )


def _sync_provider(args: argparse.Namespace, config: Config) -> int:
    if config.provider != "mempalace":
        raise Refusal("sync-provider requires --provider mempalace")
    records, excluded = _active_projection(config)
    projection_hash = _projection_hash(records)
    plan: dict[str, object] = {
        "project": config.project_slug,
        "palace_path": str(config.palace_path),
        "active_record_ids": [str(metadata["id"]) for _, metadata in records],
        "excluded_records": excluded,
        "projection_hash": projection_hash,
        "apply": bool(args.apply),
    }
    if not args.apply:
        plan["status"] = "dry-run"
        plan["safety"] = (
            "apply builds a fresh project-isolated palace, preserves a backup, "
            "then swaps only after MemPalace succeeds"
        )
        print(json.dumps(plan))
        return 0
    if os.name != "posix":
        raise Refusal(
            "safe provider replacement is supported only on POSIX; "
            "dry-run was not applied and no palace was changed"
        )

    parent = config.palace_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    projection = Path(tempfile.mkdtemp(prefix=".projection-", dir=parent))
    stage = parent / f".palace-rebuild-{uuid.uuid4().hex}"
    backup: Path | None = None
    executable = ""
    argv: list[str] = []
    try:
        _materialize_projection(records, projection)
        stage.mkdir(mode=0o700)
        executable, version = _mempalace_version(config)
        argv = [executable, "mine", str(projection), "--wing", config.project_slug]
        _run_mempalace(
            config,
            argv[1:],
            timeout=300.0,
            palace_path=stage,
        )
        if not stage.is_dir():
            raise Refusal("MemPalace did not leave a valid staged palace")
        if config.palace_path.exists():
            backup = parent / f"palace-backup-{uuid.uuid4().hex}"
            os.replace(config.palace_path, backup)
        try:
            os.replace(stage, config.palace_path)
        except OSError:
            if backup is not None and not config.palace_path.exists():
                os.replace(backup, config.palace_path)
            raise
    except (OSError, Refusal) as exc:
        receipt = _provider_receipt(
            config,
            provider_version="unknown",
            operation="sync-provider",
            artifact_hash=None,
            argv=argv,
            outcome="failed",
            detail=str(exc),
            projection_hash=projection_hash,
            backup_path=backup,
        )
        raise Refusal(
            f"provider synchronization failed; receipt={receipt}: {exc}"
        ) from exc
    finally:
        shutil.rmtree(projection, ignore_errors=True)
        if stage.exists() and stage != config.palace_path:
            shutil.rmtree(stage, ignore_errors=True)
    receipt = _provider_receipt(
        config,
        provider_version=version,
        operation="sync-provider",
        artifact_hash=None,
        argv=argv,
        outcome="success",
        detail=f"reconciled {len(records)} accepted/current records",
        projection_hash=projection_hash,
        backup_path=backup,
    )
    plan.update(
        {
            "status": "synchronized",
            "backup_path": str(backup) if backup else None,
            "receipt": str(receipt),
        }
    )
    print(json.dumps(plan))
    return 0


def _hook_timeout(event: str) -> float:
    return {"stop": 25.0, "precompact": 85.0, "session-end": 300.0}[event]


def _run_hook(event: str, config: Config, payload: bytes) -> int:
    if not config.auto_capture:
        print("{}")
        return 0
    config.project_slug
    result = _run_mempalace(
        config,
        ["hook", "run", "--hook", event, "--harness", "claude-code"],
        input_bytes=payload,
        timeout=_hook_timeout(event),
    )
    if result.stdout:
        _write_stdout(result.stdout)
    else:
        print("{}")
    return 0


def _queue_hook(event: str, config: Config, payload: bytes) -> int:
    if not config.auto_capture:
        print("{}")
        return 0
    config.project_slug
    pending_dir = config.home / "pending" / config.project_slug
    pending_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=pending_dir,
        prefix=f"{event}-",
        suffix=".json",
        delete=False,
    ) as handle:
        handle.write(payload)
        pending = Path(handle.name)
    os.chmod(pending, 0o600)
    log_dir = config.home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{config.project_slug}-hooks.log"
    worker_env = os.environ.copy()
    worker_env.update(
        {
            "CONTEXT_KIT_MEMORY_PROVIDER": config.provider,
            "CONTEXT_KIT_MEMORY_HOME": str(config.home),
            "CONTEXT_KIT_MEMORY_PROJECT": config.project or "",
            "CONTEXT_KIT_MEMORY_AUTO_CAPTURE": "true",
        }
    )
    with log_path.open("ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "hook-worker",
                event,
                str(pending),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log,
            close_fds=True,
            start_new_session=True,
            env=worker_env,
        )
    print("{}")
    return 0


def _hook_worker(event: str, pending: Path, config: Config) -> int:
    try:
        payload = pending.read_bytes()
        return _run_hook(event, config, payload)
    finally:
        pending.unlink(missing_ok=True)


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=("none", "mempalace"))
    parser.add_argument("--home")
    parser.add_argument("--project")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-provider",
        description="Validate context-kit memories and invoke an optional provider.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("artifact")

    capture = sub.add_parser("capture")
    capture.add_argument("artifact")
    capture.add_argument("--local-only", action="store_true")
    _add_config_args(capture)

    archive = sub.add_parser("archive-handoff")
    archive.add_argument("artifact")
    archive.add_argument("--local-only", action="store_true")
    archive.add_argument(
        "--repo",
        default=".",
        help="Current repository used to enforce handoff freshness.",
    )
    _add_config_args(archive)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--results", type=int, default=8)
    search.add_argument(
        "--include-inactive",
        action="store_true",
        help="Audit local proposed, rejected, stale, superseded, and revoked records.",
    )
    _add_config_args(search)

    wake = sub.add_parser("wake")
    _add_config_args(wake)

    doctor = sub.add_parser("doctor")
    _add_config_args(doctor)

    review = sub.add_parser("review")
    review.add_argument(
        "--include-inactive",
        action="store_true",
        help="Explicitly document audit intent; review already reports all records.",
    )
    _add_config_args(review)

    state = sub.add_parser("record-state")
    state.add_argument("record_id")
    state.add_argument("--review", choices=sorted(REVIEW_STATES))
    state.add_argument("--freshness", choices=sorted(FRESHNESS_STATES))
    state.add_argument("--reason", required=True)
    _add_config_args(state)

    sync = sub.add_parser("sync-provider")
    sync.add_argument(
        "--apply",
        action="store_true",
        help="Build, validate, back up, and replace the project-isolated active palace.",
    )
    _add_config_args(sync)

    hook = sub.add_parser("hook")
    hook.add_argument("event", choices=("stop", "precompact", "session-end"))
    hook.add_argument("--detach", action="store_true")
    _add_config_args(hook)

    worker = sub.add_parser("hook-worker", help=argparse.SUPPRESS)
    worker.add_argument("event", choices=("stop", "precompact", "session-end"))
    worker.add_argument("pending")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            metadata = validate_memory(Path(args.artifact).expanduser().resolve())
            print(json.dumps({"status": "valid", "id": metadata["id"]}))
            return 0

        config = _config(args)
        if args.command == "capture":
            return _capture_memory(args, config)
        if args.command == "archive-handoff":
            return _archive_handoff(args, config)
        if args.command == "search":
            if not 1 <= args.results <= 50:
                raise Refusal("--results must be between 1 and 50")
            return _search(args, config)
        if args.command == "wake":
            return _wake(config)
        if args.command == "doctor":
            return _doctor(config)
        if args.command == "review":
            return _record_review(config)
        if args.command == "record-state":
            return _record_state(args, config)
        if args.command == "sync-provider":
            return _sync_provider(args, config)
        if args.command == "hook":
            payload = sys.stdin.buffer.read()
            if args.detach:
                return _queue_hook(args.event, config, payload)
            return _run_hook(args.event, config, payload)
        if args.command == "hook-worker":
            return _hook_worker(args.event, Path(args.pending), config)
    except (OSError, Refusal) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
