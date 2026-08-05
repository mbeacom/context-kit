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
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "context-kit/memory-v1"
MAX_BYTES = 32 * 1024
MAX_MEMORY_LINES = 220
MAX_HANDOFF_LINES = 300
MAX_HANDOFF_ITEMS = 25
MAX_CUES = 3
MAX_STATE_REASON_CHARS = 1000
PROVIDER_BACKUP_RETENTION = 1
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
CANDIDATE_SCHEMA = "context-kit/memory-candidate-v1"
# Session mining recognizes GitHub Copilot CLI event logs
# (`~/.copilot/session-state/<session-id>/events.jsonl`).
SESSION_PRODUCER = "github-copilot-cli"
MAX_TURN_CHARS = 2000
MAX_CANDIDATE_TURNS = 400
# Detection only. Each pattern names a high-signal credential shape so a
# finding can be reported precisely and, with --redact, masked in place.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "json-web-token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    (
        "assigned-credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token|bearer)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_.-]{16,}"
        ),
    ),
)
PROJECTION_MARKER_SCHEMA = "context-kit/memory-provider-projection-v1"
PROJECTION_MARKER_NAME = ".context-kit-projection.json"
STATE_SEQUENCE_WIDTH = 20
STATE_LOCK_TIMEOUT_SECONDS = 5.0
STATE_LOCK_STALE_SECONDS = 300.0
STATE_SEQUENCE_RE = re.compile(r"^(\d{20})-[0-9a-f]{32}\.json$")
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
# The adapter is verified against this MemPalace release; see
# skills/memory-workflows/references/provider-mempalace.md for the
# compatibility matrix and how `doctor` reports drift.
MEMPALACE_TESTED_VERSION = (3, 6, 0)
MEMPALACE_TESTED_RELEASE_LINE = "3.6.x"
# The first-party `rag` provider is this repository's own `local-rag` plugin.
# `CONTEXT_KIT_LOCAL_RAG_HOME` (local-rag >= 0.4.0) separates venv resolution
# from index-data location, which is what lets this adapter redirect index data
# into a project-isolated store without relocating the shared venv.
RAG_TESTED_VERSION = (0, 4, 0)
RAG_TESTED_RELEASE_LINE = "0.4.x"
RAG_INDEX_NAME = "memory"
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
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
class CapabilityProbe:
    """One exact-argv help surface the adapter depends on."""

    name: str
    argv: tuple[str, ...]
    contract: str
    required_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderSpec:
    """Everything that differs between external providers.

    Keeping the differences declarative means `sync-provider`, `search`, and
    `doctor` share one projection, staging, swap, marker, and receipt path
    regardless of which provider is configured.
    """

    name: str
    # Live store directory under providers/<name>/<project-key>/. This is the
    # unit that is atomically swapped, so it must be a directory the adapter
    # owns exclusively.
    store_dirname: str
    backup_prefix: str
    bin_env: str
    executable: str
    install_hint: str
    tested_version: tuple[int, int, int]
    tested_release_line: str
    capabilities: tuple[CapabilityProbe, ...]

    def index_argv(self, projection: Path, project_key: str) -> list[str]:
        raise NotImplementedError

    def search_argv(self, query: str, results: int) -> list[str]:
        raise NotImplementedError

    def store_env(self, store: Path) -> dict[str, str]:
        """Environment that points the provider at `store` for this call only."""
        raise NotImplementedError


@dataclass(frozen=True)
class MemPalaceSpec(ProviderSpec):
    def index_argv(self, projection: Path, project_key: str) -> list[str]:
        return ["mine", str(projection), "--wing", project_key]

    def search_argv(self, query: str, results: int) -> list[str]:
        return ["search", query, "--results", str(results)]

    def store_env(self, store: Path) -> dict[str, str]:
        return {"MEMPALACE_PALACE_PATH": str(store)}


@dataclass(frozen=True)
class RagSpec(ProviderSpec):
    def index_argv(self, projection: Path, project_key: str) -> list[str]:
        # The store is already project-isolated by `store_env`, so a constant
        # index name keeps the on-disk layout readable.
        return ["index", str(projection), "--name", RAG_INDEX_NAME]

    def search_argv(self, query: str, results: int) -> list[str]:
        return ["query", query, "--name", RAG_INDEX_NAME, "--k", str(results), "--json"]

    def store_env(self, store: Path) -> dict[str, str]:
        # CONTEXT_KIT_DATA relocates *index data* into the isolated store.
        # CONTEXT_KIT_LOCAL_RAG_HOME pins the venv to its normal location so
        # redirecting data does not make `bin/rag` look for a venv that only
        # exists in the shared local-rag home.
        return {
            "CONTEXT_KIT_DATA": str(store),
            "CONTEXT_KIT_LOCAL_RAG_HOME": str(_local_rag_home()),
        }


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "mempalace": MemPalaceSpec(
        name="mempalace",
        store_dirname="palace",
        backup_prefix="palace-backup-",
        bin_env="CONTEXT_KIT_MEMPALACE_BIN",
        executable="mempalace",
        install_hint="install it separately with `uv tool install mempalace`",
        tested_version=MEMPALACE_TESTED_VERSION,
        tested_release_line=MEMPALACE_TESTED_RELEASE_LINE,
        # Each probe mirrors an exact argv the adapter actually invokes.
        # Probing `--help` (never the mutating command itself) lets `doctor`
        # catch upstream CLI drift without importing provider internals or
        # writing to a store.
        capabilities=(
            CapabilityProbe(
                name="capture",
                argv=("mine", "--help"),
                contract="mine <dir> --wing <project-key>",
                required_tokens=("--wing",),
            ),
            CapabilityProbe(
                name="search",
                argv=("search", "--help"),
                contract="search <query> --results <n>",
                required_tokens=("--results",),
            ),
            CapabilityProbe(
                name="wake",
                argv=("wake-up", "--help"),
                contract="wake-up",
            ),
        ),
    ),
    "rag": RagSpec(
        name="rag",
        store_dirname="store",
        backup_prefix="store-backup-",
        bin_env="CONTEXT_KIT_RAG_BIN",
        executable="rag",
        install_hint=(
            "install the context-kit `local-rag` plugin and run "
            "`bash plugins/local-rag/scripts/bootstrap.sh`"
        ),
        tested_version=RAG_TESTED_VERSION,
        tested_release_line=RAG_TESTED_RELEASE_LINE,
        capabilities=(
            CapabilityProbe(
                name="capture",
                argv=("index", "--help"),
                contract="index <dir> --name <index>",
                required_tokens=("--name",),
            ),
            CapabilityProbe(
                name="search",
                argv=("query", "--help"),
                contract="query <text> --name <index> --k <n> --json",
                required_tokens=("--name", "--k", "--json"),
            ),
        ),
    ),
}
PROVIDERS = ("none", *sorted(PROVIDER_SPECS))


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
    def spec(self) -> ProviderSpec:
        try:
            return PROVIDER_SPECS[self.provider]
        except KeyError:
            raise Refusal(
                f"operation requires an external provider; configured: {self.provider}"
            ) from None

    @property
    def provider_root(self) -> Path:
        return self.home / "providers" / self.spec.name / self.project_slug

    @property
    def store_path(self) -> Path:
        """The project-isolated directory swapped atomically on reconciliation."""
        return self.provider_root / self.spec.store_dirname

    @property
    def palace_path(self) -> Path:
        # Retained name for the MemPalace layout; `store_path` is the
        # provider-neutral accessor used by the shared reconciliation path.
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

    @property
    def candidates_path(self) -> Path:
        """Reviewable session extractions. Never active memory."""
        return self.home / "candidates" / self.project_slug


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _local_rag_home() -> Path:
    """Where local-rag keeps its bootstrapped venv.

    This mirrors local-rag's own resolution order and is read from the *ambient*
    environment, before this adapter redirects `CONTEXT_KIT_DATA` at the store.
    """
    configured = _first_env(
        "CONTEXT_KIT_LOCAL_RAG_HOME",
        "CONTEXT_KIT_DATA",
        "PRODUCTIVITY_SKILLS_DATA",
        "CLAUDE_PLUGIN_DATA",
    )
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".claude/plugins/data/local-rag"


def _config(args: argparse.Namespace) -> Config:
    provider = (
        getattr(args, "provider", None)
        or _first_env(
            "CONTEXT_KIT_MEMORY_PROVIDER",
            "CLAUDE_PLUGIN_OPTION_PROVIDER",
        )
        or "none"
    ).lower()
    if provider not in PROVIDERS:
        raise Refusal("memory provider must be one of: " + ", ".join(PROVIDERS))

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
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


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
    paths = list(directory.glob("*.json")) if directory.exists() else []
    sequenced = [path for path in paths if STATE_SEQUENCE_RE.fullmatch(path.name)]
    legacy = [path for path in paths if path not in sequenced]
    if sequenced and legacy:
        raise Refusal(
            "mixed legacy and sequenced state events; migrate legacy events before "
            f"recording more state for {record_id}"
        )
    if sequenced:
        return sorted(
            sequenced, key=lambda path: int(STATE_SEQUENCE_RE.fullmatch(path.name)[1])
        )
    return sorted(legacy)


@contextlib.contextmanager
def _state_lock(config: Config, record_id: str):
    """Serialize state transitions without making the evidence artifact writable."""
    parent = config.states_path / record_id
    parent.mkdir(parents=True, exist_ok=True)
    lock = parent / ".lock"
    token = uuid.uuid4().hex
    owner = lock / "owner.json"
    deadline = time.monotonic() + STATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock.mkdir()
        except FileExistsError:
            if _reclaim_stale_lock(lock):
                continue
            if time.monotonic() >= deadline:
                raise Refusal(f"state transition is busy for record: {record_id}")
            time.sleep(0.02)
            continue
        try:
            _write_once(
                owner,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "token": token,
                        "acquired_at": _utc_timestamp(),
                    },
                    sort_keys=True,
                ).encode("utf-8"),
            )
        except (OSError, Refusal):
            shutil.rmtree(lock, ignore_errors=True)
            raise
        break
    try:
        yield
    finally:
        try:
            payload = json.loads(owner.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if payload.get("token") == token:
            owner.unlink(missing_ok=True)
            lock.rmdir()


def _reclaim_stale_lock(lock: Path) -> bool:
    """Reclaim only a dead POSIX owner, or a conservatively old non-POSIX lock."""
    owner = lock / "owner.json"
    try:
        payload = json.loads(owner.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    pid = payload.get("pid")
    reclaim = False
    if os.name == "posix" and isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            reclaim = True
        except PermissionError:
            return False
    elif os.name != "posix":
        try:
            reclaim = time.time() - lock.stat().st_mtime >= STATE_LOCK_STALE_SECONDS
        except OSError:
            return False
    if not reclaim:
        return False
    retired = lock.with_name(f".lock-stale-{uuid.uuid4().hex}")
    try:
        os.replace(lock, retired)
    except OSError:
        return False
    shutil.rmtree(retired, ignore_errors=True)
    return True


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
    sequenced = STATE_SEQUENCE_RE.fullmatch(path.name)
    expected = required | {"sequence"} if sequenced else required
    if not isinstance(payload, dict) or set(payload) != expected:
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
    if sequenced and (
        not isinstance(payload["sequence"], int)
        or payload["sequence"] != int(sequenced[1])
    ):
        raise Refusal(f"state event sequence does not match its filename: {path}")
    if not isinstance(payload["reason"], str) or not payload["reason"].strip():
        raise Refusal(f"state event is missing a reason: {path}")
    if len(payload["reason"]) > MAX_STATE_REASON_CHARS:
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


def _ledger_hash(config: Config) -> str:
    """Bind provider authority to all local record and state history, not its shape."""
    digest = hashlib.sha256()
    paths: list[Path] = []
    if config.records_path.exists():
        paths.extend(config.records_path.glob("*.md"))
    if config.states_path.exists():
        paths.extend(
            path
            for path in config.states_path.rglob("*.json")
            if ".lock" not in path.relative_to(config.states_path).parts
        )
    for path in sorted(paths, key=lambda item: str(item.relative_to(config.home))):
        digest.update(str(path.relative_to(config.home)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
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
    recovery_status: str = "not-needed",
) -> Path:
    payload: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": uuid.uuid4().hex,
        "timestamp": _utc_timestamp(),
        "provider": config.spec.name,
        "provider_version": provider_version,
        "project": config.project,
        "project_key": config.project_slug,
        "store_path": str(config.store_path),
        "operation": operation,
        "artifact_hash": artifact_hash,
        "projection_hash": projection_hash,
        "argv": argv,
        "outcome": outcome,
        "detail": detail,
        "backup_path": str(backup_path) if backup_path else None,
        "recovery_status": recovery_status,
    }
    if config.spec.name == "mempalace":
        # Retained for continuity with receipts written before the adapter
        # supported more than one provider.
        payload["palace_path"] = str(config.store_path)
    return _write_json_once(config.receipts_path, payload)


def _provider_executable(spec: ProviderSpec) -> str:
    override = _first_env(spec.bin_env)
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_absolute():
            raise Refusal(f"{spec.bin_env} must be an absolute path")
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise Refusal(
                f"configured {spec.name} executable is not runnable: {candidate}"
            )
        return str(candidate)
    executable = shutil.which(spec.executable)
    if executable:
        return executable
    bundled = _bundled_executable(spec)
    if bundled is not None:
        return str(bundled)
    raise Refusal(
        f"{spec.name} provider selected but `{spec.executable}` is not installed; "
        f"{spec.install_hint}"
    )


def _local_rag_root() -> Path | None:
    """The sibling local-rag plugin root, when deployed alongside `memory`.

    `memory` hard-depends on `local-rag`, so both are installed together and
    the dependency's launcher and bootstrap are reachable without a PATH entry
    or extra configuration.
    """
    candidate = Path(__file__).resolve().parents[2] / "local-rag"
    if (candidate / "scripts" / "bootstrap.sh").is_file():
        return candidate
    return None


def _bundled_executable(spec: ProviderSpec) -> Path | None:
    """Resolve a sibling context-kit plugin launcher that is not on PATH."""
    if spec.name != "rag":
        return None
    root = _local_rag_root()
    if root is None:
        return None
    candidate = root / "bin" / "rag"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def _rag_runtime_status(*, bootstrap: bool = False) -> dict[str, object]:
    """Report whether the local-rag venv is usable, optionally building it.

    Claude Code bootstraps local-rag from a `SessionStart` hook. GitHub Copilot
    and APM do not run Claude hooks, so readiness is checked explicitly here
    rather than surfacing later as an opaque provider failure. A venv built
    from different project metadata is reported as loudly as a missing one,
    because it otherwise runs stale code silently.
    """
    root = _local_rag_root()
    if root is None:
        return {
            "status": "unknown",
            "detail": "the local-rag plugin was not found next to memory; "
            "runtime readiness could not be checked",
        }
    script = root / "scripts" / "bootstrap.sh"
    env = os.environ.copy()
    env["CONTEXT_KIT_LOCAL_RAG_HOME"] = str(_local_rag_home())
    if bootstrap:
        try:
            built = subprocess.run(
                ["bash", str(script)],
                capture_output=True,
                check=False,
                timeout=900.0,
                env=env,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise Refusal(f"local-rag bootstrap could not run: {exc}") from exc
        if built.returncode != 0:
            detail = built.stderr.decode("utf-8", errors="replace").strip()
            raise Refusal(f"local-rag bootstrap failed: {detail or 'no error output'}")
    try:
        checked = subprocess.run(
            ["bash", str(script), "--check"],
            capture_output=True,
            check=False,
            timeout=60.0,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "unknown", "detail": f"readiness check failed: {exc}"}
    report: dict[str, object] = {}
    for line in checked.stdout.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            report[key.strip()] = value.strip()
    report.setdefault("status", "unknown")
    return report


def _probe_capability(
    executable: str,
    config: Config,
    spec: ProviderSpec,
    probe: CapabilityProbe,
    *,
    timeout: float = 10.0,
) -> dict[str, object]:
    report: dict[str, object] = {
        "name": probe.name,
        "command": " ".join(probe.argv),
        "contract": probe.contract,
    }
    try:
        result = subprocess.run(
            [executable, *probe.argv],
            capture_output=True,
            check=False,
            timeout=timeout,
            env=_provider_env(config),
        )
    except subprocess.TimeoutExpired:
        report["status"] = "timeout"
        report["detail"] = f"probe timed out after {timeout:g}s"
        return report
    except OSError as exc:
        report["status"] = "error"
        report["detail"] = str(exc)
        return report
    output = "\n".join(
        (
            result.stdout.decode("utf-8", errors="replace"),
            result.stderr.decode("utf-8", errors="replace"),
        )
    )
    if result.returncode != 0:
        report["status"] = "missing"
        report["detail"] = f"`{' '.join(probe.argv)}` exited {result.returncode}"
        return report
    missing_tokens = [token for token in probe.required_tokens if token not in output]
    if missing_tokens:
        report["status"] = "incompatible"
        report["detail"] = f"missing option(s): {', '.join(missing_tokens)}"
        return report
    report["status"] = "ok"
    return report


def _parse_provider_version(raw: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.search(raw)
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch)


def _provider_version_status(
    parsed: tuple[int, int, int] | None, spec: ProviderSpec
) -> str:
    if parsed is None:
        return "unknown"
    if parsed[:2] == spec.tested_version[:2]:
        return "tested"
    if parsed[:2] < spec.tested_version[:2]:
        return "older-than-tested"
    return "newer-than-tested"


def _provider_env(config: Config, store_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    path = store_path or config.store_path
    path.parent.mkdir(parents=True, exist_ok=True)
    env.update(config.spec.store_env(path))
    return env


def _run_provider(
    config: Config,
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: float = 120.0,
    store_path: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    spec = config.spec
    executable = _provider_executable(spec)
    try:
        result = subprocess.run(
            [executable, *argv],
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=_provider_env(config, store_path),
        )
    except subprocess.TimeoutExpired as exc:
        raise Refusal(f"{spec.name} command timed out after {timeout:g}s") from exc
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise Refusal(
            f"{spec.name} exited {result.returncode}: {error or 'no error output'}"
        )
    return result


def _write_stdout(raw: bytes) -> None:
    sys.stdout.write(raw.decode("utf-8", errors="replace"))


def _provider_version(config: Config) -> tuple[str, str]:
    executable = _provider_executable(config.spec)
    version = _run_provider(config, ["--version"], timeout=20.0)
    return executable, version.stdout.decode("utf-8", errors="replace").strip()


def _capture_memory(args: argparse.Namespace, config: Config) -> int:
    source = Path(args.artifact).expanduser().resolve()
    metadata = validate_memory(source)
    _assert_project_matches(metadata, config)
    raw = source.read_bytes()
    destination = config.records_path / f"{metadata['id']}.md"
    state = _write_once(destination, raw)
    archived = False
    archive_reason = "provider not selected"
    archive_outcome = "not-selected"
    receipt: Path | None = None
    effective = effective_state(metadata, config)
    if config.provider != "none" and not args.local_only:
        if _is_active(effective):
            archive_reason = (
                "eligible for provider indexing but pending explicit "
                "sync-provider --apply"
            )
            archive_outcome = "pending-sync"
            receipt = _provider_receipt(
                config,
                operation="capture",
                provider_version="not-invoked",
                artifact_hash=str(metadata["artifact_hash"]),
                argv=[],
                outcome="pending-sync",
                detail=archive_reason,
            )
        else:
            archive_reason = (
                "not provider eligible; explicit sync will exclude this record "
                f"(review={effective['review']}, freshness={effective['freshness']})"
            )
            archive_outcome = "skipped"
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
        archive_outcome = "skipped"
    print(
        json.dumps(
            {
                "status": state,
                "artifact": str(destination),
                "project": config.project_slug,
                "provider": config.provider,
                "provider_archived": archived,
                "provider_archive": {
                    "outcome": archive_outcome,
                    "reason": archive_reason,
                    "receipt": str(receipt) if receipt else None,
                },
                "provider_reconciliation": (
                    "required: run sync-provider --apply"
                    if config.provider == "mempalace" and _is_active(effective)
                    else "not-required"
                ),
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
    if config.provider != "none" and not args.local_only:
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
                "provider_reconciliation": "not-required: handoffs are not active memory",
                "saved_head": metadata["head"],
            }
        )
    )
    return 0


def _local_search(
    args: argparse.Namespace,
    config: Config,
    *,
    annotations: dict[str, object] | None = None,
) -> int:
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
    payload: dict[str, object] = {
        "provider": "local",
        "project": config.project_slug,
        "records": results[: args.results],
        "invalid_records": invalid_records,
        "inactive_records": inactive_records,
        "include_inactive": args.include_inactive,
    }
    # A degraded provider search annotates the local result rather than
    # silently presenting lexical hits as semantic recall.
    payload.update(annotations or {})
    print(json.dumps(payload))
    return 0


def _provider_search(args: argparse.Namespace, config: Config) -> int:
    """Run a reconciled provider query. MemPalace streams; rag is enriched."""
    spec = config.spec
    if spec.name != "rag":
        result = _run_provider(config, spec.search_argv(args.query, args.results))
        _write_stdout(result.stdout)
        return 0

    records, _ = _active_projection(config)
    by_id = {str(metadata["id"]): metadata for _, metadata in records}
    result = _run_provider(config, spec.search_argv(args.query, args.results))
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    try:
        hits = json.loads(raw) if raw else []
    except json.JSONDecodeError as exc:
        raise Refusal(f"rag returned output that is not valid JSON: {exc}") from exc
    if not isinstance(hits, list):
        raise Refusal("rag returned an unexpected JSON shape; expected a list")

    found: list[dict[str, object]] = []
    unmatched: list[str] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        # The projection materializes each record as `<record-id>.md`, so a hit
        # path maps back to exactly one record id.
        path = str(hit.get("path", ""))
        record_id = path[:-3] if path.endswith(".md") else path
        metadata = by_id.get(record_id)
        if metadata is None:
            unmatched.append(path)
            continue
        state = effective_state(metadata, config)
        found.append(
            {
                "id": metadata["id"],
                "type": metadata["type"],
                "freshness": state["freshness"],
                "review": state["review"],
                "primary_memory": metadata["primary_memory"],
                "cue_anchors": metadata["cue_anchors"],
                "source": metadata["source"],
                "source_hash": metadata["source_hash"],
                "source_state": _source_state(metadata),
                "score": hit.get("score"),
                "retrieval_mode": hit.get("retrieval_mode"),
                "heading": hit.get("heading"),
            }
        )
    print(
        json.dumps(
            {
                "provider": spec.name,
                "project": config.project_slug,
                "records": found,
                # A hit the adapter cannot bind to a current record is reported,
                # never dropped: it means the index is ahead of the ledger.
                "unmatched_hits": sorted(unmatched),
                "include_inactive": False,
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
    # Reconciliation is a correctness gate, not an availability problem, so it
    # refuses outright and is deliberately outside the degradation path below.
    if not _has_current_provider_projection(config, projection_hash):
        raise Refusal(
            "provider index is not reconciled with accepted/current records; "
            "run sync-provider --apply or use --provider none for local recall"
        )
    try:
        return _provider_search(args, config)
    except Refusal as exc:
        return _local_search(
            args,
            config,
            annotations={
                "degraded_from": config.provider,
                "degraded_reason": str(exc),
                "degraded_detail": (
                    "semantic recall was unavailable; these are lexical matches "
                    "over primary memories and cue anchors only"
                ),
            },
        )


def _wake(config: Config) -> int:
    spec = config.spec
    if spec.name != "mempalace":
        records, _ = _active_projection(config)
        print(
            json.dumps(
                {
                    "provider": spec.name,
                    "project": config.project_slug,
                    "status": "not-applicable",
                    "detail": (
                        "`wake` is a MemPalace session-priming command; "
                        f"the {spec.name} provider has no equivalent"
                    ),
                    "store_path": str(config.store_path),
                    "active_records": len(records),
                    "reconciled": _has_current_provider_projection(
                        config, _projection_hash(records)
                    ),
                }
            )
        )
        return 0
    result = _run_provider(config, ["wake-up"])
    _write_stdout(result.stdout)
    return 0


def _doctor(args: argparse.Namespace, config: Config) -> int:
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
    spec = config.spec
    executable = _provider_executable(spec)
    if spec.name == "rag":
        # The venv only backs the bundled `bin/rag` launcher. A user-supplied
        # executable (CONTEXT_KIT_RAG_BIN or one on PATH) manages its own
        # runtime, so gating on our bootstrap would be wrong there.
        bundled = _bundled_executable(spec)
        if bundled is not None and str(bundled) == executable:
            # Checked before the version and capability probes: without a
            # usable venv those fail with an opaque launcher error instead of
            # the actionable "run the bootstrap" answer.
            runtime = _rag_runtime_status(
                bootstrap=bool(getattr(args, "bootstrap", False))
            )
            result["runtime"] = runtime
            status = str(runtime.get("status"))
            if status not in {"ready", "unknown"}:
                command = runtime.get("bootstrap_command") or (
                    "bash plugins/local-rag/scripts/bootstrap.sh"
                )
                raise Refusal(
                    f"the local-rag runtime is {status} "
                    f"({runtime.get('detail', 'no detail')}); run: {command} "
                    "— Claude Code bootstraps this on SessionStart, but GitHub "
                    "Copilot and APM do not run Claude hooks. Re-run `doctor "
                    "--bootstrap` to build it now."
                )
    version_result = _run_provider(config, ["--version"], timeout=20.0)
    raw_version = version_result.stdout.decode("utf-8", errors="replace").strip()
    parsed_version = _parse_provider_version(raw_version)
    version_status = _provider_version_status(parsed_version, spec)
    capabilities = [
        _probe_capability(executable, config, spec, probe)
        for probe in spec.capabilities
    ]
    missing = [c for c in capabilities if c["status"] != "ok"]
    compatibility: dict[str, object] = {
        "detected_version": raw_version,
        "parsed_version": (
            ".".join(str(part) for part in parsed_version) if parsed_version else None
        ),
        "version_status": version_status,
        "tested_release_line": spec.tested_release_line,
        "tested_version": ".".join(str(part) for part in spec.tested_version),
        "executable": executable,
        "store_path": str(config.store_path),
        "capabilities": capabilities,
    }
    if spec.name == "mempalace":
        compatibility["palace_path"] = str(config.store_path)
    result["compatibility"] = compatibility
    if missing:
        summary = "; ".join(
            f"{c['name']} ({c['command']}): {c['detail']}" for c in missing
        )
        raise Refusal(
            f"{spec.name} CLI is missing required capabilities for this adapter "
            f"(tested against {spec.tested_release_line}, detected "
            f"{raw_version or 'unknown version'}): {summary}"
        )
    # A patch/minor version different from the tested line is not on its own
    # a reason to block: only missing/incompatible capabilities are fatal.
    result.update(
        {
            "status": "ready",
            "executable": executable,
            "store_path": str(config.store_path),
            "version": raw_version,
        }
    )
    if spec.name == "mempalace":
        result["palace_path"] = str(config.store_path)
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
    if len(reason) > MAX_STATE_REASON_CHARS:
        raise Refusal(f"--reason must not exceed {MAX_STATE_REASON_CHARS} characters")
    with _state_lock(config, args.record_id):
        metadata, current = _load_record(path, config)
        requested = {
            "review": args.review if args.review is not None else current["review"],
            "freshness": (
                args.freshness if args.freshness is not None else current["freshness"]
            ),
        }
        _validate_transition(current, requested)
        existing = _event_paths(config, args.record_id)
        if existing and not STATE_SEQUENCE_RE.fullmatch(existing[0].name):
            raise Refusal(
                "legacy timestamp-named state events are replayed read-only; "
                "migrate them before recording a new transition"
            )
        sequence = (
            int(STATE_SEQUENCE_RE.fullmatch(existing[-1].name)[1]) + 1
            if existing
            else 1
        )
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
            "sequence": sequence,
        }
        raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        event = (
            config.states_path
            / args.record_id
            / f"{sequence:0{STATE_SEQUENCE_WIDTH}d}-{uuid.uuid4().hex}.json"
        )
        if _write_once(event, raw) != "created":
            raise Refusal(f"refusing to reuse a generated state event path: {event}")
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


def _write_projection_marker(
    stage: Path,
    config: Config,
    projection_hash: str,
    ledger_hash: str,
    provider_version: str,
) -> None:
    raw = (
        json.dumps(
            {
                "schema": PROJECTION_MARKER_SCHEMA,
                "project": config.project,
                "project_key": config.project_slug,
                "projection_hash": projection_hash,
                "ledger_hash": ledger_hash,
                "provider_version": provider_version,
                "applied_at": _utc_timestamp(),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    _write_once(stage / PROJECTION_MARKER_NAME, raw)


def _has_current_provider_projection(config: Config, projection_hash: str) -> bool:
    marker = config.store_path / PROJECTION_MARKER_NAME
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or set(payload) != {
        "schema",
        "project",
        "project_key",
        "projection_hash",
        "ledger_hash",
        "provider_version",
        "applied_at",
    }:
        return False
    try:
        _validate_timestamp(str(payload["applied_at"]), "applied_at")
    except Refusal:
        return False
    return (
        payload["schema"] == PROJECTION_MARKER_SCHEMA
        and payload["project"] == config.project
        and payload["project_key"] == config.project_slug
        and payload["projection_hash"] == projection_hash
        and payload["ledger_hash"] == _ledger_hash(config)
        and isinstance(payload["provider_version"], str)
    )


def _prune_provider_backups(
    parent: Path, keep: Path | None, prefix: str = "palace-backup-"
) -> list[str]:
    backups = [
        path for path in parent.glob(f"{prefix}*") if path.is_dir() and path != keep
    ]
    if keep is None:
        backups.sort(
            key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True
        )
        backups = backups[PROVIDER_BACKUP_RETENTION:]
    removed: list[str] = []
    for path in backups:
        shutil.rmtree(path)
        removed.append(str(path))
    return sorted(removed)


def _sync_provider(args: argparse.Namespace, config: Config) -> int:
    if config.provider == "none":
        raise Refusal(
            "sync-provider requires an external provider; choose one of: "
            + ", ".join(sorted(PROVIDER_SPECS))
        )
    spec = config.spec
    records, excluded = _active_projection(config)
    projection_hash = _projection_hash(records)
    ledger_hash = _ledger_hash(config)
    plan: dict[str, object] = {
        "project": config.project_slug,
        "provider": spec.name,
        "store_path": str(config.store_path),
        "active_record_ids": [str(metadata["id"]) for _, metadata in records],
        "excluded_records": excluded,
        "projection_hash": projection_hash,
        "apply": bool(args.apply),
    }
    if spec.name == "mempalace":
        plan["palace_path"] = str(config.store_path)
    if not args.apply:
        plan["status"] = "dry-run"
        plan["safety"] = (
            "apply builds a fresh project-isolated store, preserves a backup, "
            f"then swaps only after {spec.name} succeeds"
        )
        print(json.dumps(plan))
        return 0
    if os.name != "posix":
        raise Refusal(
            "safe provider replacement is supported only on POSIX; "
            "dry-run was not applied and no store was changed"
        )

    parent = config.store_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    projection = Path(tempfile.mkdtemp(prefix=".projection-", dir=parent))
    stage = parent / f".store-rebuild-{uuid.uuid4().hex}"
    backup: Path | None = None
    executable = ""
    version = "unknown"
    argv: list[str] = []
    recovery_status = "not-needed"
    try:
        _materialize_projection(records, projection)
        stage.mkdir(mode=0o700)
        executable, version = _provider_version(config)
        argv = [executable, *spec.index_argv(projection, config.project_slug)]
        _run_provider(
            config,
            argv[1:],
            timeout=300.0,
            store_path=stage,
        )
        if not stage.is_dir():
            raise Refusal(f"{spec.name} did not leave a valid staged store")
        _write_projection_marker(
            stage,
            config,
            projection_hash,
            ledger_hash,
            version,
        )
        if config.store_path.exists():
            backup = parent / f"{spec.backup_prefix}{uuid.uuid4().hex}"
            os.replace(config.store_path, backup)
        try:
            os.replace(stage, config.store_path)
        except OSError:
            if backup is not None and not config.store_path.exists():
                os.replace(backup, config.store_path)
                backup = None
                recovery_status = "restored-to-live-store"
            elif backup is not None:
                recovery_status = "backup-preserved"
            raise
    except (OSError, Refusal) as exc:
        receipt = _provider_receipt(
            config,
            provider_version=version,
            operation="sync-provider",
            artifact_hash=None,
            argv=argv,
            outcome="failed",
            detail=str(exc),
            projection_hash=projection_hash,
            backup_path=backup,
            recovery_status=recovery_status,
        )
        raise Refusal(
            f"provider synchronization failed; receipt={receipt}: {exc}"
        ) from exc
    finally:
        shutil.rmtree(projection, ignore_errors=True)
        if stage.exists() and stage != config.store_path:
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
    try:
        removed_backups = _prune_provider_backups(parent, backup, spec.backup_prefix)
    except OSError as exc:
        raise Refusal(
            "provider synchronized but backup retention failed; "
            f"receipt={receipt}: {exc}"
        ) from exc
    plan.update(
        {
            "status": "synchronized",
            "backup_path": str(backup) if backup else None,
            "removed_backups": removed_backups,
            "receipt": str(receipt),
        }
    )
    print(json.dumps(plan))
    return 0


def _extract_copilot_session(raw: bytes) -> dict[str, object] | None:
    """Extract the human-visible conversation from a Copilot CLI event log.

    Copilot records *all* session activity in one event stream, so most events
    are not conversation. Attribution matters more than volume here: a subagent
    task prompt is written by the orchestrating model, not by the person, and
    storing it as a user turn silently misattributes authorship.

    Measured across a real 115-session corpus, only 24 of 729 `user.message`
    events were human-authored; 611 carried `parentAgentTaskId` (subagent task
    prompts) and 94 carried a `source` (generated skill/agent/command/system
    context). Every distinct `source` value observed was generated context, so
    the presence of the field — not a specific prefix — is the reliable signal.

    Returns None when the input is not a recognized Copilot session. A
    recognized session with no conversational turns returns an empty turn list
    rather than None, so the caller can record it as empty instead of falling
    back to raw event JSON.
    """
    text = raw.decode("utf-8", errors="replace")
    session_id: str | None = None
    started_at: str | None = None
    producer: str | None = None
    turns: list[dict[str, str]] = []
    dropped: dict[str, int] = {
        "user_subagent_prompt": 0,
        "user_generated_context": 0,
        "user_empty": 0,
        "assistant_tool_nested": 0,
        "assistant_subagent": 0,
        "assistant_empty": 0,
        "non_conversational_event": 0,
        "unparsable_line": 0,
    }

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            dropped["unparsable_line"] += 1
            continue
        if not isinstance(event, dict):
            dropped["unparsable_line"] += 1
            continue
        kind = event.get("type", "")
        data = event.get("data", {})
        if not isinstance(data, dict):
            dropped["non_conversational_event"] += 1
            continue

        if kind == "session.start":
            candidate_id = data.get("sessionId")
            if isinstance(candidate_id, str) and candidate_id:
                session_id = candidate_id
                start_time = data.get("startTime")
                if isinstance(start_time, str) and start_time:
                    started_at = start_time
                produced_by = data.get("producer")
                if isinstance(produced_by, str) and produced_by:
                    producer = produced_by
            continue

        if session_id is None:
            # Nothing before a recognized session.start is trusted.
            dropped["non_conversational_event"] += 1
            continue

        if kind == "user.message":
            if data.get("parentAgentTaskId"):
                dropped["user_subagent_prompt"] += 1
                continue
            if "source" in data:
                # Generated context: skill-, agent-, command-, or system.
                # A human turn carries no source at all.
                dropped["user_generated_context"] += 1
                continue
            role = "user"
        elif kind == "assistant.message":
            if data.get("parentToolCallId"):
                dropped["assistant_tool_nested"] += 1
                continue
            if data.get("parentAgentTaskId"):
                dropped["assistant_subagent"] += 1
                continue
            role = "assistant"
        else:
            dropped["non_conversational_event"] += 1
            continue

        # `content` is what the person actually wrote. `transformedContent`
        # is post-expansion, and reasoning fields are never retained.
        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            dropped[f"{role}_empty"] += 1
            continue
        turns.append({"role": role, "content": content.strip()})

    if session_id is None:
        return None
    return {
        "session_id": session_id,
        "started_at": started_at,
        "producer": producer,
        "turns": turns,
        "dropped": dropped,
    }


def _scan_secrets(text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for name, pattern in SECRET_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            findings.append({"pattern": name, "matches": count})
    return findings


def _redact_secrets(text: str) -> tuple[str, int]:
    redactions = 0
    for name, pattern in SECRET_PATTERNS:
        text, count = pattern.subn(f"[redacted:{name}]", text)
        redactions += count
    return text, redactions


def _render_turns(turns: list[dict[str, str]]) -> tuple[list[str], int]:
    lines: list[str] = []
    truncated = 0
    for index, turn in enumerate(turns[:MAX_CANDIDATE_TURNS], start=1):
        content = turn["content"]
        if len(content) > MAX_TURN_CHARS:
            content = content[:MAX_TURN_CHARS]
            truncated += 1
            content += f"\n\n[truncated at {MAX_TURN_CHARS} characters]"
        lines.append(f"### {index}. {turn['role']}")
        lines.append("")
        lines.extend(content.splitlines())
        lines.append("")
    return lines, truncated


def _propose_from_session(args: argparse.Namespace, config: Config) -> int:
    """Extract reviewable candidates from Copilot CLI sessions.

    This deliberately proposes rather than captures. A transcript is not an
    atomic memory, so authoring a `memory-v1` record from a candidate stays an
    explicit judgment step; nothing here can enter active recall on its own.
    """
    root = Path(args.path).expanduser().resolve()
    if root.is_file():
        logs = [root]
    elif root.is_dir():
        logs = sorted(root.glob("*/events.jsonl")) or sorted(root.glob("events.jsonl"))
    else:
        raise Refusal(f"session path does not exist: {root}")
    if not logs:
        raise Refusal(f"no Copilot `events.jsonl` logs found under {root}")

    repo = Path(args.repo).expanduser().resolve()
    repository = _normalize_repository(_git(repo, "remote", "get-url", "origin"))
    _assert_project_matches({"repository": repository, "scope": "project"}, config)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git(repo, "rev-parse", "HEAD")
    if branch == "HEAD":
        # Detached checkouts (CI PR builds, a worktree at a tag, bisect) have no
        # branch anchor, and a project record requires one. Say so plainly
        # instead of refusing with a generic name-format error.
        raise Refusal(
            f"{repo} is in a detached HEAD state, so there is no branch anchor "
            "for a project record. Check out a named branch, or pass --repo "
            "pointing at a checkout that is on one."
        )
    _validate_branch(branch)

    planned: list[dict[str, object]] = []
    written: list[str] = []
    blocked: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for log in logs:
        raw = log.read_bytes()
        extracted = _extract_copilot_session(raw)
        if extracted is None:
            skipped.append({"source": str(log), "reason": "not-a-copilot-session"})
            continue
        turns = list(extracted["turns"])  # type: ignore[arg-type]
        if not turns:
            skipped.append({"source": str(log), "reason": "no-conversational-turns"})
            continue

        body_lines, truncated = _render_turns(turns)
        transcript = "\n".join(body_lines)
        findings = _scan_secrets(transcript)
        redactions = 0
        if findings:
            if not args.redact:
                blocked.append(
                    {
                        "source": str(log),
                        "reason": "possible-credentials",
                        "findings": findings,
                    }
                )
                continue
            transcript, redactions = _redact_secrets(transcript)

        source_hash = hashlib.sha256(raw).hexdigest()
        session_id = str(extracted["session_id"])
        observed_at = extracted["started_at"] or _utc_timestamp()
        try:
            _validate_timestamp(str(observed_at), "observed_at")
        except Refusal:
            observed_at = _utc_timestamp()
        entry: dict[str, object] = {
            "session_id": session_id,
            "source": str(log),
            "source_hash": source_hash,
            "turns": len(turns),
            "dropped": extracted["dropped"],
            "truncated_turns": truncated,
            "redactions": redactions,
        }
        if args.dry_run:
            planned.append(entry)
            continue

        name = f"{session_id}-{source_hash[:12]}.md"
        destination = config.candidates_path / name
        document = "\n".join(
            [
                "---",
                f"schema: {CANDIDATE_SCHEMA}",
                f"session_id: {session_id}",
                "scope: project",
                f"repository: {repository}",
                f"branch: {branch}",
                f"head: {head}",
                f"producer: {extracted['producer'] or SESSION_PRODUCER}",
                f"observed_at: {observed_at}",
                f"extracted_at: {_utc_timestamp()}",
                f"source: {log}",
                f"source_hash: {source_hash}",
                f"turns: {len(turns)}",
                f"redactions: {redactions}",
                "review: candidate",
                "---",
                "",
                "## Provenance",
                "",
                f"- Extracted from `{log}` (SHA-256 `{source_hash}`).",
                "- Only top-level human and assistant turns are retained. Subagent",
                "  prompts, generated skill/agent/command context, tool-nested",
                "  messages, and model reasoning are excluded by construction.",
                "",
                "## Dropped Events",
                "",
                *(
                    f"- {reason}: {count}"
                    for reason, count in sorted(
                        dict(extracted["dropped"]).items()  # type: ignore[arg-type]
                    )
                    if count
                ),
                "",
                "## Transcript",
                "",
                transcript,
                "",
                "## Review Notes",
                "",
                "- This is a candidate, not a memory. To retain anything here,",
                "  author a `context-kit/memory-v1` record whose `source` is the",
                "  session log above and whose `source_hash` matches, mark it",
                "  `review: proposed`, then promote it with `record-state` only",
                "  after checking the evidence.",
                "",
            ]
        )
        state = _write_once(destination, document.encode("utf-8"))
        entry["artifact"] = str(destination)
        entry["status"] = state
        written.append(str(destination))
        planned.append(entry)

    print(
        json.dumps(
            {
                "status": "dry-run" if args.dry_run else "extracted",
                "project": config.project_slug,
                "repository": repository,
                "branch": branch,
                "head": head,
                "logs_examined": len(logs),
                "candidates": planned,
                "written": written,
                "blocked": blocked,
                "skipped": skipped,
                "note": (
                    "candidates are proposals for review; nothing here enters "
                    "active recall until an explicit memory-v1 record is "
                    "captured and accepted"
                ),
            }
        )
    )
    return 0


def _run_hook(event: str, config: Config, payload: bytes) -> int:
    if not config.auto_capture:
        print("{}")
        return 0
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"hook payload must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise Refusal("hook payload must be a JSON object")
    pending_dir = config.home / "pending-hooks" / config.project_slug
    pending = _new_write_once_path(pending_dir, f"-{event}.json")
    if _write_once(pending, payload) != "created":
        raise Refusal(f"refusing to reuse a generated hook payload path: {pending}")
    print(
        json.dumps(
            {
                "status": "queued-for-review",
                "event": event,
                "pending": str(pending),
                "provider_invoked": False,
            }
        )
    )
    return 0


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=PROVIDERS)
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
    doctor.add_argument(
        "--bootstrap",
        action="store_true",
        help="Build the local-rag runtime if it is missing or stale (rag provider).",
    )
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

    propose = sub.add_parser("propose-from-session")
    propose.add_argument("path", help="A Copilot session directory or events.jsonl.")
    propose.add_argument(
        "--repo",
        default=".",
        help="Repository supplying the project, branch, and HEAD anchors.",
    )
    propose.add_argument(
        "--write",
        dest="dry_run",
        action="store_false",
        help="Write candidate artifacts. Without this the run is a dry run.",
    )
    propose.add_argument(
        "--redact",
        action="store_true",
        help="Mask detected credential-shaped spans instead of refusing.",
    )
    propose.set_defaults(dry_run=True)
    _add_config_args(propose)

    hook = sub.add_parser("hook")
    hook.add_argument("event", choices=("stop", "precompact", "session-end"))
    _add_config_args(hook)
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
            return _doctor(args, config)
        if args.command == "review":
            return _record_review(config)
        if args.command == "record-state":
            return _record_state(args, config)
        if args.command == "sync-provider":
            return _sync_provider(args, config)
        if args.command == "propose-from-session":
            return _propose_from_session(args, config)
        if args.command == "hook":
            payload = sys.stdin.buffer.read()
            return _run_hook(args.event, config, payload)
    except (OSError, Refusal) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
