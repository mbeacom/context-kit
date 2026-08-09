#!/usr/bin/env python3
"""Run one plugin-owned read-only inspection operation and emit bounded output.

Unlike the runtime-evidence runner, the allowlist here is *not* operator-supplied.
This script ships the exact set of non-mutating inspection operations `verify`
will run, keyed by an operation ID. Read-only is a property of this code, not of
a config file a caller could widen. The runner builds each argv itself from
validated parameters, never from a shell string, so the mutation and execution
vectors that a prefix-matched command grant would still admit cannot be reached.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_TIMEOUT_SECONDS = 120.0
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_OUTPUT_BYTES = 1_048_576
DEFAULT_OUTPUT_BYTES = 262_144
MAX_COUNT = 10_000
MAX_PARAM_LENGTH = 4096
MAX_PARAMS = 16
TERMINATION_GRACE_SECONDS = 0.5

REV_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^-]{0,199}$")
FIELD_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class Refusal(ValueError):
    """A policy or input refusal: nothing was executed."""


class Unavailable(ValueError):
    """A requested enforced operation cannot run in this environment."""


def _validate_platform(platform_name: str) -> None:
    if platform_name != "posix":
        raise Refusal(
            "the inspection runner requires a POSIX platform because its bounded "
            "non-blocking pipe capture and process-group termination are not "
            "supported on Windows"
        )


@dataclass(frozen=True)
class Param:
    name: str
    kind: str
    required: bool
    description: str
    default: str | None = None


@dataclass(frozen=True)
class Operation:
    id: str
    tool: str
    modality: str
    summary: str
    params: tuple[Param, ...]
    build: Callable[[dict[str, str]], list[str]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Parameter validation ---------------------------------------------------
#
# Each value is validated by kind and returned as the literal argv fragment the
# build function will position itself. A path is confined to the analysis root; a
# revision, field, or count is shape-checked. No value is ever concatenated into
# a flag string, so a value that looks like a write flag or an in-place flag
# cannot become one.


def _validate_count(raw: str) -> str:
    if not raw.isdigit():
        raise Refusal("count must be a non-negative integer")
    value = int(raw)
    if not 1 <= value <= MAX_COUNT:
        raise Refusal(f"count must be between 1 and {MAX_COUNT}")
    return str(value)


def _validate_rev(raw: str) -> str:
    if not REV_RE.fullmatch(raw):
        raise Refusal(
            "revision must start with a letter or digit and use only "
            "[A-Za-z0-9._/~^-]; a leading dash is refused so it cannot become a flag"
        )
    return raw


def _validate_pattern(raw: str) -> str:
    if not raw or "\0" in raw or len(raw) > MAX_PARAM_LENGTH:
        raise Refusal("pattern must be non-empty, NUL-free, and within the length cap")
    return raw


def _validate_field(raw: str) -> str:
    segments = raw.split(".")
    if not segments or any(not FIELD_SEGMENT_RE.fullmatch(seg) for seg in segments):
        raise Refusal(
            "field must be a dotted path of [A-Za-z0-9_-] segments; the runner "
            "assembles the filter, so no raw jq/yq expression is accepted"
        )
    # Encode each segment as a JSON-quoted bracket key: `.["a"]["b"]`. A bare
    # dotted filter is unsafe for both jq and yq -- `.release-name` parses as
    # subtraction (`.release` minus `name`) and `.2fa` is a syntax error -- so an
    # accepted segment could silently address the wrong thing or fail to run.
    # json.dumps keeps the quoting correct if FIELD_SEGMENT_RE is ever widened.
    return "." + "".join(f"[{json.dumps(seg)}]" for seg in segments)


def _validate_path(raw: str, root: Path) -> str:
    if not raw or "\0" in raw or len(raw) > MAX_PARAM_LENGTH:
        raise Refusal("path must be non-empty, NUL-free, and within the length cap")
    if raw.startswith("-"):
        raise Refusal("path must not start with a dash")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise Refusal("path must be relative to the analysis root")
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise Refusal("path escapes the analysis root")
    relative = resolved.relative_to(root_resolved)
    return relative.as_posix() if relative.parts else "."


def _validate_value(kind: str, raw: str, root: Path) -> str:
    if kind == "count":
        return _validate_count(raw)
    if kind == "rev":
        return _validate_rev(raw)
    if kind == "pattern":
        return _validate_pattern(raw)
    if kind == "field":
        return _validate_field(raw)
    if kind == "path":
        return _validate_path(raw, root)
    raise Refusal(f"unknown parameter kind: {kind}")


# --- Operation catalog ------------------------------------------------------
#
# The catalog is an allowlist of permitted argument shapes, not a denylist of bad
# flags. A denylist is a losing game: new mutation or exec flags can be added to a
# tool at any release, so enumerating them can never be complete. Instead every
# argv here is fixed except for positionally substituted, validated parameters,
# and each command carries the global flags that neutralize its own known write
# and exec surfaces (`--no-pager`, `--no-color`).
#
# GIT_HARDENING pins the program-executing repository-local config settings that
# environment variables do not cover. GIT_CONFIG_GLOBAL/SYSTEM neutralize only
# global and system config; git still reads the analysis root's own .git/config,
# which can define program-running settings. These runner-owned `-c` overrides are
# fixed and are never derived from a parameter. Issue #27 named *caller-supplied*
# `-c` as an injection vector; that stays impossible here precisely because a
# caller can never reach this list.
#
# core.fsmonitor= (empty) disables a repo-local fsmonitor hook without error.
# diff.external and a diff driver's textconv are *not* neutralized by setting the
# config key to empty -- git then tries to run the empty string as a program and
# dies. The purpose-built flags `--no-ext-diff` and `--no-textconv` are the
# correct disable, and they are applied per operation below on the commands that
# can invoke a diff driver (see _git_diff_family).
GIT_HARDENING: tuple[str, ...] = (
    "-c",
    "core.fsmonitor=",
    "-c",
    "core.pager=cat",
)


def _git(*args: str) -> list[str]:
    return ["git", *GIT_HARDENING, "--no-pager", *args]


def _op_git_log_path(v: dict[str, str]) -> list[str]:
    return _git(
        "log",
        "--no-color",
        f"--max-count={v['max_count']}",
        "--",
        v["path"],
    )


def _op_git_log_recent(v: dict[str, str]) -> list[str]:
    return _git(
        "log",
        "--no-color",
        "--oneline",
        f"--max-count={v['max_count']}",
    )


def _op_git_show_commit(v: dict[str, str]) -> list[str]:
    return _git(
        "show", "--no-color", "--no-ext-diff", "--no-textconv", "--stat", v["rev"]
    )


def _op_git_diff_revs(v: dict[str, str]) -> list[str]:
    argv = _git(
        "diff", "--no-color", "--no-ext-diff", "--no-textconv", v["base"], v["head"]
    )
    if "path" in v:
        argv += ["--", v["path"]]
    return argv


def _op_git_blame_path(v: dict[str, str]) -> list[str]:
    return _git("blame", "--no-color", "--no-textconv", "--", v["path"])


def _op_git_grep(v: dict[str, str]) -> list[str]:
    # --basic-regexp pins the documented pattern kind. git grep otherwise honors
    # the repository-local grep.patternType, which GIT_CONFIG_GLOBAL/SYSTEM do not
    # reach, so a repo set to extended/perl/fixed would silently change what this
    # operation means. The flag is runner-owned and overrides that repo config.
    argv = _git("grep", "-n", "--no-color", "--basic-regexp", "-e", v["pattern"])
    if "path" in v:
        argv += ["--", v["path"]]
    return argv


def _op_json_keys(v: dict[str, str]) -> list[str]:
    return ["jq", "--sort-keys", "keys", v["path"]]


def _op_json_field(v: dict[str, str]) -> list[str]:
    return ["jq", v["field"], v["path"]]


def _op_json_paths(v: dict[str, str]) -> list[str]:
    return ["jq", "-c", "paths", v["path"]]


def _op_json_type(v: dict[str, str]) -> list[str]:
    return ["jq", "type", v["path"]]


def _op_yaml_keys(v: dict[str, str]) -> list[str]:
    return ["yq", "keys", v["path"]]


def _op_yaml_field(v: dict[str, str]) -> list[str]:
    return ["yq", v["field"], v["path"]]


# adrkit is optional and contributor-side (ADR-0003). It is invoked as an exact
# argv like every other tool here, so it must be on PATH as `adr`; when it is
# not, the runner reports `unavailable` and the governance modality is recorded
# as unreached rather than silently skipped. Both operations are read-only:
# `explain` and `check` never mutate the corpus, make no model calls, and open
# no sockets.
def _op_adr_explain(v: dict[str, str]) -> list[str]:
    return ["adr", "explain", v["path"], "--dir", v["dir"], "--json"]


def _op_adr_check(v: dict[str, str]) -> list[str]:
    return ["adr", "check", v["path"], "--dir", v["dir"], "--json"]


_ADR_DIR = Param("dir", "path", False, "ADR corpus directory", default="docs/adr")


_PATH = Param("path", "path", True, "repo-relative file or directory in the root")
_OPT_PATH = Param("path", "path", False, "optional repo-relative path filter")
_COUNT = Param("max_count", "count", False, "commit limit (1-10000)", default="20")

OPERATIONS: tuple[Operation, ...] = (
    Operation(
        "git-log-path",
        "git",
        "history",
        "Commit history touching a path (read-only).",
        (_PATH, _COUNT),
        _op_git_log_path,
    ),
    Operation(
        "git-log-recent",
        "git",
        "history",
        "Recent commit subjects across the repository.",
        (_COUNT,),
        _op_git_log_recent,
    ),
    Operation(
        "git-show-commit",
        "git",
        "history",
        "One commit's message and changed-file stat.",
        (Param("rev", "rev", True, "a commit-ish (SHA or ref)"),),
        _op_git_show_commit,
    ),
    Operation(
        "git-diff-revs",
        "git",
        "history",
        "Diff between two revisions, optionally scoped to a path.",
        (
            Param("base", "rev", True, "base revision"),
            Param("head", "rev", True, "head revision"),
            _OPT_PATH,
        ),
        _op_git_diff_revs,
    ),
    Operation(
        "git-blame-path",
        "git",
        "history",
        "Line-level authorship for a tracked file.",
        (_PATH,),
        _op_git_blame_path,
    ),
    Operation(
        "git-grep",
        "git",
        "structural",
        "Search tracked file contents, optionally under a path.",
        (
            Param(
                "pattern",
                "pattern",
                True,
                "basic regular expression (git grep --basic-regexp -e) over "
                "tracked content",
            ),
            _OPT_PATH,
        ),
        _op_git_grep,
    ),
    Operation(
        "json-keys",
        "jq",
        "structured-data",
        "Top-level keys of a JSON document.",
        (_PATH,),
        _op_json_keys,
    ),
    Operation(
        "json-field",
        "jq",
        "structured-data",
        "Value at a dotted field path in a JSON document.",
        (_PATH, Param("field", "field", True, "dotted field path, e.g. a.b.c")),
        _op_json_field,
    ),
    Operation(
        "json-paths",
        "jq",
        "structured-data",
        "Enumerate every path in a JSON document.",
        (_PATH,),
        _op_json_paths,
    ),
    Operation(
        "json-type",
        "jq",
        "structured-data",
        "Top-level type of a JSON document.",
        (_PATH,),
        _op_json_type,
    ),
    Operation(
        "yaml-keys",
        "yq",
        "structured-data",
        "Top-level keys of a YAML document (mikefarah yq).",
        (_PATH,),
        _op_yaml_keys,
    ),
    Operation(
        "yaml-field",
        "yq",
        "structured-data",
        "Value at a dotted field path in a YAML document (mikefarah yq).",
        (_PATH, Param("field", "field", True, "dotted field path, e.g. a.b.c")),
        _op_yaml_field,
    ),
    Operation(
        "adr-explain-path",
        "adr",
        "governance",
        "Architecture decisions governing a path, with rejected and superseded "
        "ones (adrkit; read-only, offline).",
        (_PATH, _ADR_DIR),
        _op_adr_explain,
    ),
    Operation(
        "adr-check-path",
        "adr",
        "governance",
        "Conformance of a path against the decisions that govern it (adrkit; "
        "read-only, offline).",
        (_PATH, _ADR_DIR),
        _op_adr_check,
    ),
)

OPERATIONS_BY_ID = {operation.id: operation for operation in OPERATIONS}


def _catalog() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operations": [
            {
                "id": operation.id,
                "tool": operation.tool,
                "modality": operation.modality,
                "summary": operation.summary,
                "params": [
                    {
                        "name": param.name,
                        "kind": param.kind,
                        "required": param.required,
                        "description": param.description,
                        "default": param.default,
                    }
                    for param in operation.params
                ],
            }
            for operation in OPERATIONS
        ],
    }


# --- Environment hardening --------------------------------------------------
#
# Start from an empty environment and add only what the inspection tools need.
# This is the allowlist approach again: every GIT_* redirection variable
# (GIT_DIR, GIT_WORK_TREE, GIT_EXTERNAL_DIFF, GIT_SSH*, GIT_CONFIG*, GIT_PAGER,
# ...) is dropped by construction rather than enumerated, and config and pagers
# are pinned to inert values so global or system config cannot redirect behavior
# into a write or exec. HOME is deliberately not forwarded, so a per-user rc file
# a tool would otherwise autoload (~/.gitconfig, ~/.jq) is unreachable too.


def _analysis_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_ALLOW_PROTOCOL": "",
    }


# --- Bounded capture --------------------------------------------------------
#
# Ported from the runtime-evidence runner: a per-stream byte cap with a visible
# truncation flag, a wall-clock timeout, and a process-group kill that still fires
# after the child closes its output pipes or spawns descendants.


def _stop_process_group(process: subprocess.Popen[bytes]) -> str:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
            return "process-group-killed"
        if process.poll() is not None:
            return "process-already-exited"
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
    for name, stream in {"stdout": process.stdout, "stderr": process.stderr}.items():
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
    termination_deadline: float | None = None

    while selector.get_map() or process.poll() is None:
        now = time.monotonic()
        elapsed = now - started
        if wrapper_exit is None and elapsed >= timeout:
            termination_reason = "timeout"
            wrapper_exit = 124
            cleanup_status = _stop_process_group(process)
            termination_deadline = now + TERMINATION_GRACE_SECONDS

        if termination_deadline is not None and now >= termination_deadline:
            for key in list(selector.get_map().values()):
                stream = key.fileobj
                selector.unregister(stream)
                stream.close()
            break

        wait = 0.05
        if wrapper_exit is None:
            wait = min(wait, max(0.0, timeout - elapsed))
        elif termination_deadline is not None:
            wait = min(wait, max(0.0, termination_deadline - now))
        events = selector.select(wait) if selector.get_map() else ()
        if not events and not selector.get_map() and process.poll() is None:
            time.sleep(wait)
        for key, _mask in events:
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
                    termination_deadline = time.monotonic() + TERMINATION_GRACE_SECONDS

    try:
        child_exit = process.wait(timeout=TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        cleanup_status = _stop_process_group(process)
        try:
            child_exit = process.wait(timeout=TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            child_exit = process.returncode if process.returncode is not None else -9
            cleanup_status = f"{cleanup_status}; process-exit-unconfirmed"
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


# --- Request assembly -------------------------------------------------------


def _parse_params(items: list[str]) -> dict[str, str]:
    if len(items) > MAX_PARAMS:
        raise Refusal(f"at most {MAX_PARAMS} parameters are accepted")
    values: dict[str, str] = {}
    for item in items:
        name, sep, raw = item.partition("=")
        if not sep or not name:
            raise Refusal(f"parameter must be name=value: {item!r}")
        if name in values:
            raise Refusal(f"parameter {name} was provided more than once")
        values[name] = raw
    return values


def _resolve_operation(
    operation: Operation, raw_params: dict[str, str], root: Path
) -> dict[str, str]:
    allowed = {param.name for param in operation.params}
    unknown = set(raw_params) - allowed
    if unknown:
        raise Refusal(
            f"operation {operation.id} does not accept: {', '.join(sorted(unknown))}"
        )
    resolved: dict[str, str] = {}
    for param in operation.params:
        if param.name in raw_params:
            resolved[param.name] = _validate_value(
                param.kind, raw_params[param.name], root
            )
        elif param.required:
            raise Refusal(f"operation {operation.id} requires parameter {param.name}")
        elif param.default is not None:
            resolved[param.name] = _validate_value(param.kind, param.default, root)
    return resolved


def _clamp(value: float | None, default: float, ceiling: float, label: str) -> float:
    if value is None:
        return default
    if value <= 0:
        raise Refusal(f"{label} must be positive")
    return min(value, ceiling)


def _report(
    *,
    operation: Operation,
    argv: list[str],
    root: Path,
    resolved: dict[str, str],
    env_keys: list[str],
    captured: dict[str, bytes],
    truncated: dict[str, bool],
    started_at: str,
    finished_at: str,
    termination_reason: str,
    cleanup_status: str,
    exit_code: int,
    spawn_error: str | None,
) -> dict[str, Any]:
    limitations = [
        (
            "The operation catalog is plugin-owned and read-only by construction; "
            "it still cannot prove the installed tool has no side effects."
        ),
        (
            "Empty output is scoped negative evidence for this operation, not "
            "proof of absence."
        ),
        "Host command policy is independent of this runner.",
    ]
    if termination_reason == "timeout":
        limitations.append("The operation exceeded its timeout; output is incomplete.")
    if termination_reason == "output-limit":
        limitations.append(
            "An output stream exceeded its cap; later bytes were dropped."
        )
    if spawn_error:
        limitations.append("The operation could not be spawned in this environment.")

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
        "status": "executed",
        "operation": operation.id,
        "tool": operation.tool,
        "modality": operation.modality,
        "root": str(root),
        "argv": argv,
        "params": resolved,
        "environment": {
            "keys": env_keys,
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "observations": observations,
        "limitations": limitations,
        "started_at": started_at,
        "finished_at": finished_at,
        "cleanup_status": cleanup_status,
    }


def _emit_refusal(message: str, *, status: str, code: int) -> int:
    payload = {"error": message, "status": status}
    if status == "unavailable":
        payload["operations_hint"] = "run with --list to see enforceable operations"
    print(json.dumps(payload), file=sys.stderr)
    return code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one plugin-owned read-only inspection operation and print a "
            "bounded JSON report. The operation set is not caller-supplied."
        )
    )
    parser.add_argument(
        "--list", action="store_true", help="list enforceable operations"
    )
    parser.add_argument("--operation")
    parser.add_argument("--root")
    parser.add_argument("--param", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--max-output-bytes", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.list:
        print(json.dumps(_catalog(), indent=2))
        return 0

    try:
        _validate_platform(os.name)
        if not args.operation:
            raise Refusal("provide --operation ID (or --list to discover operations)")
        operation = OPERATIONS_BY_ID.get(args.operation)
        if operation is None:
            raise Refusal(f"operation ID is not enforceable: {args.operation}")

        raw_root = args.root or os.environ.get("CONTEXT_KIT_IMPACT_ROOT")
        if not raw_root:
            raise Refusal("provide --root or set CONTEXT_KIT_IMPACT_ROOT")
        root = Path(raw_root).expanduser()
        if not root.is_absolute() or not root.is_dir():
            raise Refusal("root must be an existing absolute directory")
        root = root.resolve()

        raw_params = _parse_params(args.param)
        resolved = _resolve_operation(operation, raw_params, root)
        timeout = _clamp(
            args.timeout_seconds,
            DEFAULT_TIMEOUT_SECONDS,
            MAX_TIMEOUT_SECONDS,
            "timeout-seconds",
        )
        output_limit = int(
            _clamp(
                args.max_output_bytes,
                DEFAULT_OUTPUT_BYTES,
                MAX_OUTPUT_BYTES,
                "max-output-bytes",
            )
        )
        command = operation.build(resolved)
        if shutil.which(command[0]) is None:
            raise Unavailable(
                f"operation {operation.id} needs {operation.tool}, which is not "
                "installed; report this modality as unreached rather than delegating"
            )
    except Unavailable as exc:
        return _emit_refusal(str(exc), status="unavailable", code=3)
    except Refusal as exc:
        return _emit_refusal(str(exc), status="refused", code=2)

    env = _analysis_env()
    started_at = _utc_now()
    spawn_error: str | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            env=env,
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
        operation=operation,
        argv=command,
        root=root,
        resolved=resolved,
        env_keys=sorted(env),
        captured=captured,
        truncated=truncated,
        started_at=started_at,
        finished_at=finished_at,
        termination_reason=reason,
        cleanup_status=cleanup,
        exit_code=exit_code,
        spawn_error=spawn_error,
    )
    print(json.dumps(report))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
