#!/usr/bin/env python3
"""Run one exact allowlisted argv and emit bounded runtime evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_TIMEOUT_SECONDS = 300.0
MAX_OUTPUT_BYTES = 1_048_576
MAX_ARGV_ITEMS = 128
MAX_ARG_LENGTH = 4096
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Refusal(ValueError):
    """A pre-execution policy or input refusal."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refuse(message: str) -> int:
    print(json.dumps({"error": message, "status": "refused"}), file=sys.stderr)
    return 2


def _resolve_required_path(
    explicit: str | None,
    env_name: str,
    *,
    suffix: str | None = None,
) -> Path:
    raw = explicit or os.environ.get(env_name)
    if not raw:
        raise Refusal(f"provide the argument or set {env_name}")
    path = Path(raw).expanduser()
    if suffix and not explicit:
        path = path / suffix
    return path.resolve()


def _validate_config_permissions(path: Path) -> None:
    if not path.is_file():
        raise Refusal(f"config is not a file: {path}")
    metadata = path.stat()
    if hasattr(os, "geteuid"):
        if metadata.st_uid != os.geteuid():
            raise Refusal("config must be owned by the current effective user")
        if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise Refusal("config must not be group- or world-writable")


def _validate_command_entry(
    command_id: str, entry: object
) -> tuple[list[str], float, int]:
    required = {"argv", "timeout_seconds", "max_output_bytes"}
    if not isinstance(entry, dict) or set(entry) != required:
        raise Refusal(
            f"command {command_id} must contain exactly argv, "
            "timeout_seconds, and max_output_bytes"
        )

    argv = entry["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > MAX_ARGV_ITEMS
        or any(not isinstance(item, str) or not item or "\0" in item for item in argv)
        or any(len(item) > MAX_ARG_LENGTH for item in argv)
    ):
        raise Refusal(f"command {command_id} has invalid argv")

    timeout = entry["timeout_seconds"]
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < float(timeout) <= MAX_TIMEOUT_SECONDS
    ):
        raise Refusal(f"timeout_seconds must be > 0 and <= {MAX_TIMEOUT_SECONDS:g}")

    output_limit = entry["max_output_bytes"]
    if (
        isinstance(output_limit, bool)
        or not isinstance(output_limit, int)
        or not 0 < output_limit <= MAX_OUTPUT_BYTES
    ):
        raise Refusal(f"max_output_bytes must be > 0 and <= {MAX_OUTPUT_BYTES}")

    return argv, float(timeout), output_limit


def _load_command(path: Path, command_id: str) -> tuple[list[str], float, int, str]:
    _validate_config_permissions(path)
    try:
        raw = path.read_bytes()
        config = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal(f"cannot read valid JSON config: {exc}") from exc

    if not isinstance(config, dict) or set(config) != {"version", "commands"}:
        raise Refusal("config must contain exactly version and commands")
    if (
        isinstance(config["version"], bool)
        or not isinstance(config["version"], int)
        or config["version"] != 1
    ):
        raise Refusal("config version must be 1")
    commands = config["commands"]
    if not isinstance(commands, dict):
        raise Refusal("commands must be an object")
    validated: dict[str, tuple[list[str], float, int]] = {}
    for configured_id, entry in commands.items():
        if not isinstance(configured_id, str) or not ID_RE.fullmatch(configured_id):
            raise Refusal(f"config contains an invalid command ID: {configured_id!r}")
        validated[configured_id] = _validate_command_entry(configured_id, entry)

    if not ID_RE.fullmatch(command_id):
        raise Refusal("command ID has an invalid format")
    if command_id not in validated:
        raise Refusal(f"command ID is not allowlisted: {command_id}")

    digest = hashlib.sha256(raw).hexdigest()
    argv, timeout, output_limit = validated[command_id]
    return argv, timeout, output_limit, digest


def _artifact_paths(directory: Path, run_id: str) -> dict[str, Path]:
    if not RUN_ID_RE.fullmatch(run_id):
        raise Refusal(
            "run ID must contain only letters, numbers, dot, underscore, or hyphen"
        )
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise Refusal(f"artifact path is not a directory: {directory}")
    paths = {
        "stdout": directory / f"{run_id}.stdout",
        "stderr": directory / f"{run_id}.stderr",
        "report": directory / f"{run_id}.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise Refusal(f"refusing to overwrite artifacts: {', '.join(existing)}")
    return paths


def _stop_process_group(process: subprocess.Popen[bytes]) -> str:
    if process.poll() is not None:
        return "process-already-exited"
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
            return "process-group-killed"
        process.kill()
        return "process-killed"
    except ProcessLookupError:
        return "process-already-exited"


def _capture(
    process: subprocess.Popen[bytes],
    timeout: float,
    output_limit: int,
) -> tuple[dict[str, bytes], dict[str, bool], str, str, int]:
    selector = selectors.DefaultSelector()
    streams = {"stdout": process.stdout, "stderr": process.stderr}
    for name, stream in streams.items():
        if stream is None:
            continue
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)

    captured = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    started = time.monotonic()
    termination_reason = "completed"
    cleanup_status = "not-needed"
    wrapper_exit: int | None = None

    while selector.get_map():
        elapsed = time.monotonic() - started
        if wrapper_exit is None and elapsed >= timeout:
            termination_reason = "timeout"
            wrapper_exit = 124
            cleanup_status = _stop_process_group(process)

        wait = 0.05
        if wrapper_exit is None:
            wait = min(wait, max(0.0, timeout - elapsed))
        for key, _mask in selector.select(wait):
            stream = key.fileobj
            name = key.data
            try:
                chunk = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(stream)
                stream.close()
                continue

            remaining = output_limit - len(captured[name])
            if remaining > 0:
                captured[name].extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[name] = True
                if wrapper_exit is None:
                    termination_reason = "output-limit"
                    wrapper_exit = 125
                    cleanup_status = _stop_process_group(process)

    child_exit = process.wait()
    if wrapper_exit is None:
        wrapper_exit = child_exit if child_exit >= 0 else 128 + abs(child_exit)
        if wrapper_exit != 0:
            termination_reason = "child-nonzero"

    return (
        {name: bytes(data) for name, data in captured.items()},
        truncated,
        termination_reason,
        cleanup_status,
        wrapper_exit,
    )


def _report(
    *,
    args: argparse.Namespace,
    config_path: Path,
    config_digest: str,
    paths: dict[str, Path],
    captured: dict[str, bytes],
    truncated: dict[str, bool],
    started_at: str,
    finished_at: str,
    termination_reason: str,
    cleanup_status: str,
    exit_code: int,
    spawn_error: str | None = None,
) -> dict[str, Any]:
    limitations = [
        "The allowlist constrains command selection but cannot prove the command has no side effects.",
        "Process termination does not reverse filesystem, database, network, or external-service effects.",
        "Host-level Bash permissions are separate from this wrapper.",
    ]
    if termination_reason == "timeout":
        limitations.append(
            "The command exceeded its timeout; observations are incomplete."
        )
    if termination_reason == "output-limit":
        limitations.append(
            "At least one output stream exceeded its cap; later bytes were not retained."
        )
    if spawn_error:
        limitations.append(
            "The configured command could not be spawned in this environment."
        )

    observations: dict[str, Any] = {
        "exit_code": exit_code,
        "termination_reason": termination_reason,
        "stdout_bytes": len(captured["stdout"]),
        "stderr_bytes": len(captured["stderr"]),
        "stdout_truncated": truncated["stdout"],
        "stderr_truncated": truncated["stderr"],
        "stdout_excerpt": captured["stdout"].decode("utf-8", errors="replace"),
        "stderr_excerpt": captured["stderr"].decode("utf-8", errors="replace"),
    }
    if spawn_error:
        observations["spawn_error"] = spawn_error

    return {
        "schema_version": 1,
        "claim": args.claim,
        "reproduction_command_id": args.command_id,
        "environment": {
            "label": args.environment_label,
            "cwd": str(Path(args.cwd).resolve()),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "observations": observations,
        "artifact_output_pointers": {
            "report": str(paths["report"]),
            "stdout": str(paths["stdout"]),
            "stderr": str(paths["stderr"]),
            "config": str(config_path),
            "config_sha256": config_digest,
        },
        "verdict_ready_evidence": {
            "process_exit_code": exit_code,
            "termination_reason": termination_reason,
            "stdout_observed": bool(captured["stdout"]),
            "stderr_observed": bool(captured["stderr"]),
            "output_truncated": any(truncated.values()),
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "limitations": limitations,
        "cleanup_status": cleanup_status,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an exact user-allowlisted command and capture bounded evidence."
    )
    parser.add_argument("--config")
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--artifact-dir")
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config_path = _resolve_required_path(
            args.config, "CONTEXT_KIT_RUNTIME_EVIDENCE_CONFIG"
        )
        artifact_dir = _resolve_required_path(
            args.artifact_dir,
            "CONTEXT_KIT_DATA",
            suffix="runtime-evidence",
        )
        cwd = Path(args.cwd).expanduser()
        if not cwd.is_absolute() or not cwd.is_dir():
            raise Refusal("cwd must be an existing absolute directory")
        args.cwd = str(cwd.resolve())
        if not args.claim.strip():
            raise Refusal("claim must not be empty")
        if not args.environment_label.strip():
            raise Refusal("environment label must not be empty")

        command, timeout, output_limit, config_digest = _load_command(
            config_path, args.command_id
        )
        paths = _artifact_paths(artifact_dir, args.run_id)
    except Refusal as exc:
        return _refuse(str(exc))

    started_at = _utc_now()
    spawn_error: str | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=args.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
        captured, truncated, reason, cleanup, exit_code = _capture(
            process, timeout, output_limit
        )
    except OSError as exc:
        captured = {"stdout": b"", "stderr": b""}
        truncated = {"stdout": False, "stderr": False}
        reason = "spawn-error"
        cleanup = "not-started"
        exit_code = 126
        spawn_error = f"{type(exc).__name__}: {exc}"

    finished_at = _utc_now()
    report = _report(
        args=args,
        config_path=config_path,
        config_digest=config_digest,
        paths=paths,
        captured=captured,
        truncated=truncated,
        started_at=started_at,
        finished_at=finished_at,
        termination_reason=reason,
        cleanup_status=cleanup,
        exit_code=exit_code,
        spawn_error=spawn_error,
    )
    paths["stdout"].write_bytes(captured["stdout"])
    paths["stderr"].write_bytes(captured["stderr"])
    paths["report"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
