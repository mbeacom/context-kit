#!/usr/bin/env python3
"""Validate durable memories and invoke an optional MemPalace provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = "context-kit/memory-v1"
MAX_BYTES = 32 * 1024
MAX_LINES = 220
MAX_CUES = 3
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
MEMORY_TYPES = {"fact", "decision", "procedure", "constraint", "episode"}
SCOPES = {"project", "personal"}
FRESHNESS_STATES = {"current", "stale", "superseded", "revoked"}
REVIEW_STATES = {"proposed", "accepted", "rejected"}
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
        if not PROJECT_RE.fullmatch(self.project):
            raise Refusal(
                "memory project must start with an alphanumeric character and use "
                "only letters, numbers, dot, underscore, slash, or hyphen"
            )
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", self.project).strip("-").lower()
        if not slug or len(slug) > 96:
            raise Refusal("memory project resolves to an invalid or overlong scope")
        return slug

    @property
    def palace_path(self) -> Path:
        return self.home / "providers" / "mempalace" / self.project_slug / "palace"


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
    if parsed.tzinfo is None:
        raise Refusal(f"{field} must include a timezone")


def _sections(body: list[str], headings: tuple[str, ...]) -> dict[str, list[str]]:
    found = [line for line in body if line.startswith("## ")]
    if found != list(headings):
        raise Refusal("artifact headings are missing, reordered, or unexpected")
    positions = [body.index(heading) for heading in headings]
    result: dict[str, list[str]] = {}
    for index, heading in enumerate(headings):
        end = positions[index + 1] if index + 1 < len(positions) else len(body)
        result[heading] = body[positions[index] + 1 : end]
    return result


def _nonempty_section(lines: list[str], heading: str) -> str:
    text = "\n".join(lines).strip()
    if not text or text == "- None.":
        raise Refusal(f"{heading} must not be empty")
    return text


def _read_bounded(path: Path) -> tuple[bytes, str]:
    if not path.is_file():
        raise Refusal(f"artifact is not a file: {path}")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise Refusal(f"artifact exceeds {MAX_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("artifact must be UTF-8") from exc
    if len(text.splitlines()) > MAX_LINES:
        raise Refusal(f"artifact exceeds {MAX_LINES} lines")
    return raw, text


def validate_memory(path: Path) -> dict[str, str]:
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
        raise Refusal(f"memory scope must be one of {sorted(SCOPES)}")
    if fields["freshness"] not in FRESHNESS_STATES:
        raise Refusal(f"freshness must be one of {sorted(FRESHNESS_STATES)}")
    if fields["review"] not in REVIEW_STATES:
        raise Refusal(f"review must be one of {sorted(REVIEW_STATES)}")
    if not HASH_RE.fullmatch(fields["source_hash"]):
        raise Refusal("source_hash must be a lowercase SHA-256 digest")
    _validate_timestamp(fields["observed_at"], "observed_at")
    _validate_timestamp(fields["captured_at"], "captured_at")
    if fields["scope"] == "project":
        for field in ("repository", "branch", "head"):
            if fields[field].lower() in {"none", "unknown"}:
                raise Refusal(f"project memory requires a concrete {field}")

    sections = _sections(body, MEMORY_HEADINGS)
    primary = _nonempty_section(sections["## Primary Memory"], "Primary Memory")
    if len(primary) > 600:
        raise Refusal("Primary Memory must be at most 600 characters")
    _nonempty_section(sections["## Evidence"], "Evidence")

    cues = [
        line[2:].strip()
        for line in sections["## Cue Anchors"]
        if line.startswith("- ") and line.strip() != "- None."
    ]
    if len(cues) > MAX_CUES:
        raise Refusal(f"Cue Anchors may contain at most {MAX_CUES} entries")
    if any(not cue or len(cue) > 120 for cue in cues):
        raise Refusal("each cue anchor must contain 1..120 characters")

    source = Path(fields["source"]).expanduser()
    if source.is_file():
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != fields["source_hash"]:
            raise Refusal("source_hash does not match the referenced source file")
    return {**fields, "artifact_hash": hashlib.sha256(raw).hexdigest()}


def validate_handoff(path: Path) -> dict[str, str]:
    raw, text = _read_bounded(path)
    fields, body = _parse_frontmatter(text)
    missing = [field for field in HANDOFF_FIELDS if field not in fields]
    if missing:
        raise Refusal(f"handoff is missing required fields: {', '.join(missing)}")
    if fields["schema"] != "context-kit/handoff-v1":
        raise Refusal("handoff schema must be context-kit/handoff-v1")
    _validate_timestamp(fields["generated_at"], "generated_at")
    if fields["worktree_state"] not in {"clean", "dirty"}:
        raise Refusal("handoff worktree_state must be clean or dirty")
    sections = _sections(body, HANDOFF_HEADINGS)
    _nonempty_section(sections["## Scope"], "Scope")
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


def _assert_handoff_current(metadata: dict[str, str], repo: Path) -> None:
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
    if destination.exists():
        if destination.read_bytes() == raw:
            return "unchanged"
        raise Refusal(f"refusing to overwrite a different artifact: {destination}")
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        handle.write(raw)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    temporary.replace(destination)
    return "created"


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


def _provider_env(config: Config) -> dict[str, str]:
    env = os.environ.copy()
    config.palace_path.parent.mkdir(parents=True, exist_ok=True)
    env["MEMPALACE_PALACE_PATH"] = str(config.palace_path)
    return env


def _run_mempalace(
    config: Config,
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: float = 120.0,
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
            env=_provider_env(config),
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


def _archive_with_provider(config: Config, directory: Path) -> None:
    _run_mempalace(
        config,
        ["mine", str(directory), "--wing", config.project_slug],
        timeout=300.0,
    )


def _capture_memory(args: argparse.Namespace, config: Config) -> int:
    source = Path(args.artifact).expanduser().resolve()
    metadata = validate_memory(source)
    raw = source.read_bytes()
    destination = config.home / "records" / config.project_slug / f"{metadata['id']}.md"
    state = _write_once(destination, raw)
    archived = False
    if config.provider == "mempalace" and not args.local_only:
        _archive_with_provider(config, destination.parent)
        archived = True
    print(
        json.dumps(
            {
                "status": state,
                "artifact": str(destination),
                "project": config.project_slug,
                "provider": config.provider,
                "provider_archived": archived,
            }
        )
    )
    return 0


def _archive_handoff(args: argparse.Namespace, config: Config) -> int:
    source = Path(args.artifact).expanduser().resolve()
    metadata = validate_handoff(source)
    _assert_handoff_current(metadata, Path(args.repo).expanduser().resolve())
    raw = source.read_bytes()
    name = (
        f"handoff-{metadata['generated_at'][:10]}-{metadata['artifact_hash'][:12]}.md"
    )
    destination = config.home / "handoffs" / config.project_slug / name
    state = _write_once(destination, raw)
    archived = False
    if config.provider == "mempalace" and not args.local_only:
        _archive_with_provider(config, destination.parent)
        archived = True
    print(
        json.dumps(
            {
                "status": state,
                "artifact": str(destination),
                "project": config.project_slug,
                "provider": config.provider,
                "provider_archived": archived,
                "saved_head": metadata["head"],
            }
        )
    )
    return 0


def _search(args: argparse.Namespace, config: Config) -> int:
    config.project_slug
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
        result["status"] = "disabled"
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
    directory = config.home / "records" / config.project_slug
    results: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.md")) if directory.exists() else []:
        try:
            metadata = validate_memory(path)
            source = Path(metadata["source"]).expanduser()
            source_state = "verified" if source.is_file() else "unavailable"
            results.append(
                {
                    "id": metadata["id"],
                    "artifact": str(path),
                    "freshness": metadata["freshness"],
                    "review": metadata["review"],
                    "source_state": source_state,
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
    print(json.dumps({"project": config.project_slug, "records": results}))
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
    _add_config_args(search)

    wake = sub.add_parser("wake")
    _add_config_args(wake)

    doctor = sub.add_parser("doctor")
    _add_config_args(doctor)

    review = sub.add_parser("review")
    _add_config_args(review)

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
