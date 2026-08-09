#!/usr/bin/env python3
"""Stdio MCP server exposing context-kit durable memory.

Standard library only. Every operation shells out to the `memorykit` provider
CLI with exact argv and no shell, so contract validation, project isolation,
review state, and reconciliation have exactly one implementation and the CLI and
MCP surfaces cannot drift apart.

The surface is deliberately small. A connected MCP server advertises its tool
schemas into the model's context on every turn, so each tool has a standing
cost; only operations that genuinely need live local state or an action are
exposed. `sync-provider`, `record-state` promotion, backup pruning, and session
mining stay explicit CLI operations.

# @adr 0009
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SERVER_NAME = "context-kit-memory"
SERVER_VERSION = "0.3.0"
# Newest first. The client's requested version is echoed when supported.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
# The provider is this package's sibling module, so one path is correct in both
# deployment shapes (ADR-0009): `plugins/memory/src/memorykit/` in the catalog
# and `site-packages/memorykit/` from a `pip install`. It is invoked as a script
# rather than imported so a provider crash cannot take down the server loop, and
# by path rather than `-m memorykit.provider` so an in-tree run needs no
# PYTHONPATH.
PROVIDER = Path(__file__).resolve().with_name("provider.py")
CALL_TIMEOUT_SECONDS = 120.0
MAX_RECORD_BYTES = 32 * 1024

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

TOOLS: list[dict[str, Any]] = [
    {
        "name": "memory_recall",
        "description": (
            "Search reviewed durable memory for this project. Returns "
            "accepted/current records only, as candidate leads whose cited "
            "source must still be checked against current code."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What you are trying to remember.",
                },
                "results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum records to return (default 8).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_capture",
        "description": (
            "Persist a context-kit/memory-v1 record as review: proposed. The "
            "record must cite real evidence: its source_hash is verified "
            "against the source file. Proposed records are inert until a human "
            "accepts them with the record-state CLI."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "record": {
                    "type": "string",
                    "description": (
                        "Complete memory-v1 markdown: flat YAML frontmatter "
                        "plus Primary Memory, Cue Anchors, Evidence, "
                        "Supersedes, and Review Notes sections."
                    ),
                }
            },
            "required": ["record"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_review",
        "description": (
            "List this project's memory records with their effective review "
            "and freshness state, including inactive ones. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    """A tool-level failure reported to the model, not a protocol error."""


def _log(message: str) -> None:
    # stdout carries only JSON-RPC frames.
    print(f"{SERVER_NAME}: {message}", file=sys.stderr, flush=True)


def _project_scope() -> str:
    for name in ("CONTEXT_KIT_MEMORY_PROJECT", "CLAUDE_PLUGIN_OPTION_PROJECT"):
        # Portable first, then the Claude userConfig fallback the CLI accepts.
        # Checking only the portable name would make every tool refuse on a
        # normal Claude install configured through the plugin's option.
        project = os.environ.get(name, "").strip()
        if project:
            return project
    raise ToolError(
        "no memory project is configured; set CONTEXT_KIT_MEMORY_PROJECT to "
        "an explicit owner/repository. Memory is never read from or written "
        "to an inferred global store."
    )


def _run_provider(argv: list[str]) -> str:
    if not PROVIDER.is_file():
        raise ToolError(f"memory provider script is missing: {PROVIDER}")
    project = _project_scope()
    command = [sys.executable, str(PROVIDER), *argv, "--project", project]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(
            f"memory command timed out after {CALL_TIMEOUT_SECONDS:g}s"
        ) from exc
    except OSError as exc:
        raise ToolError(f"memory command could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ToolError(detail or f"memory command exited {result.returncode}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _frontmatter_value(record: str, field: str) -> str | None:
    lines = record.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == field:
            return value.strip()
    return None


def _tool_memory_recall(arguments: dict[str, Any]) -> str:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolError("`query` must be a non-empty string")
    results = arguments.get("results", 8)
    if not isinstance(results, int) or isinstance(results, bool):
        raise ToolError("`results` must be an integer")
    if not 1 <= results <= 50:
        raise ToolError("`results` must be between 1 and 50")
    return _run_provider(["search", query, "--results", str(results)])


def _tool_memory_capture(arguments: dict[str, Any]) -> str:
    record = arguments.get("record")
    if not isinstance(record, str) or not record.strip():
        raise ToolError("`record` must be a non-empty memory-v1 document")
    raw = record.encode("utf-8")
    if len(raw) > MAX_RECORD_BYTES:
        raise ToolError(
            f"record exceeds {MAX_RECORD_BYTES} bytes; keep a memory atomic"
        )
    review = _frontmatter_value(record, "review")
    if review is None:
        raise ToolError("record is missing flat YAML frontmatter with a `review` field")
    if review != "proposed":
        # `capture` takes the initial state from frontmatter, so without this
        # guard an agent could write `review: accepted` and activate a memory
        # with no human review at all.
        raise ToolError(
            "this surface can only propose memory, but the record declares "
            f"review: {review}. Set `review: proposed` and promote it later "
            "with `memory-provider.py record-state <id> --review accepted "
            "--reason ...` after the evidence has been checked."
        )
    # `validate_memory` verifies `source_hash` only when the source is a
    # *regular file* (`source.is_file()`), so `exists()` here would be a weaker
    # gate than the one it exists to mirror: a record citing a directory would
    # pass this check, skip hash verification entirely, and persist with any
    # 64-character hash and unverifiable provenance. Match the provider.
    source = _frontmatter_value(record, "source")
    if not source:
        raise ToolError("record is missing a `source` field citing its evidence")
    if not Path(source).expanduser().is_file():
        raise ToolError(
            f"the cited source is not a readable file: {source}. A memory must "
            "point at evidence that can be re-read and hashed."
        )
    handle, temporary = tempfile.mkstemp(prefix="memory-capture-", suffix=".md")
    path = Path(temporary)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
        return _run_provider(["capture", str(path)])
    finally:
        path.unlink(missing_ok=True)


def _tool_memory_review(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ToolError("`memory_review` takes no arguments")
    return _run_provider(["review"])


HANDLERS = {
    "memory_recall": _tool_memory_recall,
    "memory_capture": _tool_memory_capture,
    "memory_review": _tool_memory_review,
}


def _negotiate(requested: Any) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOLS:
        return requested
    return SUPPORTED_PROTOCOLS[0]


def _tool_result(request_id: Any, text: str, *, is_error: bool) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        },
    }


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    is_notification = "id" not in request

    if method == "initialize":
        params = request.get("params") or {}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": _negotiate(params.get("protocolVersion")),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if isinstance(method, str) and method.startswith("notifications/"):
        return None

    if is_notification:
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "`arguments` must be an object")
        handler = HANDLERS.get(name) if isinstance(name, str) else None
        if handler is None:
            return _error(request_id, INVALID_PARAMS, f"unknown tool: {name!r}")
        try:
            output = handler(arguments)
        except ToolError as exc:
            # Tool failures are results, not protocol errors, so the model can
            # read the refusal and act on it.
            return _tool_result(request_id, str(exc), is_error=True)
        except Exception as exc:  # noqa: BLE001 - never kill the server loop
            _log(f"unexpected failure in {name}: {exc}")
            return _tool_result(request_id, f"unexpected failure: {exc}", is_error=True)
        return _tool_result(request_id, output or "{}", is_error=False)

    return _error(request_id, METHOD_NOT_FOUND, f"unknown method: {method!r}")


def _write(sink: Any, payload: dict[str, Any]) -> None:
    sink.write(json.dumps(payload) + "\n")
    sink.flush()


def serve(stdin: Any = None, stdout: Any = None) -> int:
    source = stdin if stdin is not None else sys.stdin
    sink = stdout if stdout is not None else sys.stdout
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write(sink, _error(None, PARSE_ERROR, f"invalid JSON: {exc}"))
            continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            _write(
                sink, _error(None, INVALID_REQUEST, "expected a JSON-RPC 2.0 object")
            )
            continue
        try:
            response = _handle(request)
        except Exception as exc:  # noqa: BLE001 - a bad frame must not end the loop
            _log(f"internal error: {exc}")
            response = _error(request.get("id"), INTERNAL_ERROR, str(exc))
        if response is not None:
            _write(sink, response)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point for `memorykit-mcp`.

    Takes no arguments: an MCP server is configured by the client that spawns
    it, over stdio. Anything on argv is a caller mistake — most likely a CLI
    subcommand aimed at the wrong entry point — so it is refused rather than
    silently ignored, which would hang the caller on a stdio read.
    """
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print(
            f"{SERVER_NAME}: this is a stdio MCP server and takes no arguments; "
            f"got {arguments!r}. For the CLI, run `memorykit --help`.",
            file=sys.stderr,
        )
        return 2
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
