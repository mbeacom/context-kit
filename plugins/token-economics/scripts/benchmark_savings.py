#!/usr/bin/env python3
"""Settle a token-savings claim with a controlled A/B run.

A compaction tool's advertised percentage describes the author's corpus, not
yours. This runs a baseline command and a candidate command against the same
work and measures what an agent would actually have to read.

The rule this script enforces: **a savings number is only meaningful alongside
evidence that the answer survived.** Truncating output to nothing "saves" 100%,
so a run without a preserved-answer assertion is reported as ``unverified`` and
exits non-zero. Passing ``--no-assertion`` is allowed but permanently downgrades
the claim rather than silently blessing it.

Every result carries two grades:

* ``counting`` — ``estimated`` when token counts come from the bytes-per-token
  heuristic, or ``tiktoken`` when that optional library is installed. No offline
  tokenizer exists for Claude models, so exactness is never claimed for them.
* ``attribution`` — always ``controlled`` here. Only the command changed between
  arms, so the difference is causal. Usage read from session telemetry is
  ``observational`` and cannot support the same claim.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from re import Pattern
from typing import Any

SCHEMA = "context-kit/token-savings-v1"

# Widely cited average for English text; source code trends denser. Used only
# when no tokenizer is installed, and always reported as `estimated`.
DEFAULT_BYTES_PER_TOKEN = 4.0

# A savings claim below this magnitude is within the noise of prompt phrasing
# and corpus choice, so it is reported as inconclusive rather than as a win.
MATERIALITY_THRESHOLD_PCT = 5.0

# Captured output is held in memory, so an arm that floods stdout would
# otherwise exhaust the host before any verdict could be reached. Past this many
# bytes the arm is stopped and its measurement is rejected rather than truncated
# into a smaller-looking, and therefore falsely cheaper, result.
DEFAULT_MAX_CAPTURE_BYTES = 64 * 1024 * 1024

_READ_CHUNK = 65536


class BenchmarkError(RuntimeError):
    """The benchmark could not produce a comparable pair of arms."""


def count_tokens(data: bytes, encoder: Any | None) -> tuple[int, str]:
    """Return ``(tokens, grade)`` for captured output.

    The heuristic divides UTF-8 **bytes**, not code points. Dividing characters
    would score an emoji or box-drawing glyph as a quarter token while it costs
    four bytes and several real tokens, which is enough to invert a verdict when
    a candidate trades ASCII for symbols.
    """
    if encoder is not None:
        try:
            text = data.decode("utf-8", errors="replace")
            return len(encoder.encode(text, disallowed_special=())), "tiktoken"
        except Exception:  # pragma: no cover - defensive, encoder is optional
            pass
    if not data:
        return 0, "estimated"
    # Rounding alone sends one or two bytes to zero, which downstream reads as an
    # empty arm and reports "produced no output" about output that exists. Zero
    # is reserved for genuinely empty captures.
    return max(1, int(round(len(data) / DEFAULT_BYTES_PER_TOKEN))), "estimated"


def load_encoder(name: str | None) -> tuple[Any | None, list[str]]:
    """Load a tiktoken encoding when requested and available."""
    notes: list[str] = []
    if not name:
        return None, notes
    try:
        import tiktoken  # type: ignore
    except ImportError:
        notes.append(
            f"tiktoken is not installed; falling back to the "
            f"{DEFAULT_BYTES_PER_TOKEN:g} bytes-per-token heuristic"
        )
        return None, notes
    try:
        return tiktoken.get_encoding(name), notes
    except Exception as exc:
        notes.append(
            f"tiktoken encoding {name!r} unavailable ({exc}); using the heuristic"
        )
        return None, notes


@dataclass
class Run:
    exit_code: int
    data: bytes
    duration_s: float
    truncated: bool = False

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")


@dataclass
class Arm:
    label: str
    command: str
    runs: list[Run] = field(default_factory=list)
    bytes_len: int = 0
    tokens: int = 0
    counting: str = "estimated"
    deterministic: bool = True
    exit_codes: list[int] = field(default_factory=list)
    assertion_ok: bool | None = None
    truncated: bool = False

    @property
    def median_duration(self) -> float:
        return statistics.median(r.duration_s for r in self.runs) if self.runs else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "command": self.command,
            "bytes": self.bytes_len,
            "tokens": self.tokens,
            "counting": self.counting,
            "deterministic": self.deterministic,
            "exit_codes": self.exit_codes,
            "median_duration_s": round(self.median_duration, 4),
            "assertion_ok": self.assertion_ok,
            "truncated": self.truncated,
        }


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    """Kill a arm and everything it spawned, then reap it.

    The child is started in its own session, so killing the process group also
    removes descendants. Without this a timed-out pipeline keeps running and the
    machine stays busy long after the benchmark reports a timeout.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - kernel refused to reap
        pass


def execute(
    command: str,
    use_shell: bool,
    timeout: float,
    max_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
) -> Run:
    """Run one arm and capture, boundedly, everything an agent would read."""
    if use_shell:
        popen_args: Any = command
    else:
        try:
            popen_args = shlex.split(command)
        except ValueError as exc:
            # An unbalanced quote is a setup mistake, not a failed comparison,
            # so it must not reach the verdict exit codes.
            raise BenchmarkError(f"cannot parse command {command!r}: {exc}") from exc
        if not popen_args:
            raise BenchmarkError(f"empty command: {command!r}")

    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            popen_args,
            shell=use_shell,
            stdout=subprocess.PIPE,
            # An agent pays for stderr too. Merging at the OS level keeps the
            # read loop single-threaded, so it cannot deadlock on a full pipe.
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        # Covers a missing binary, a directory, and a non-executable file.
        raise BenchmarkError(f"cannot run {command!r}: {exc}") from exc

    chunks: list[bytes] = []
    total = 0
    truncated = False
    timed_out = threading.Event()

    def on_deadline() -> None:
        # A blocking read cannot observe a deadline on its own, so the timeout
        # is enforced by killing the arm from a watchdog. Killing the group
        # closes the pipe, which ends the read loop below with EOF.
        timed_out.set()
        _terminate(proc)

    watchdog = threading.Timer(timeout, on_deadline)
    watchdog.daemon = True
    watchdog.start()

    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                truncated = True
                _terminate(proc)
                break
            chunks.append(chunk)
    finally:
        watchdog.cancel()
        try:
            proc.stdout.close()
        except OSError:  # pragma: no cover - stream already gone
            pass

    try:
        code = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - kernel refused to reap
        _terminate(proc)
        code = -9
    duration = time.monotonic() - started

    if timed_out.is_set():
        raise BenchmarkError(f"command timed out after {timeout}s: {command}")
    return Run(code, b"".join(chunks), duration, truncated)


def check_assertion(
    text: str, must_contain: list[str], must_match: list[Pattern[str]]
) -> bool:
    for needle in must_contain:
        if needle not in text:
            return False
    for pattern in must_match:
        if not pattern.search(text):
            return False
    return True


def measure(
    label: str,
    command: str,
    *,
    runs: int,
    use_shell: bool,
    timeout: float,
    encoder: Any | None,
    must_contain: list[str],
    must_match: list[Pattern[str]],
    max_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
) -> Arm:
    arm = Arm(label=label, command=command)
    for _ in range(runs):
        arm.runs.append(execute(command, use_shell, timeout, max_bytes))
    payloads = [r.data for r in arm.runs]
    arm.exit_codes = [r.exit_code for r in arm.runs]
    arm.deterministic = len(set(payloads)) == 1
    arm.truncated = any(r.truncated for r in arm.runs)
    # With varying output, the median length is the honest representative.
    representative = sorted(payloads, key=len)[len(payloads) // 2]
    arm.bytes_len = len(representative)
    arm.tokens, arm.counting = count_tokens(representative, encoder)
    if must_contain or must_match:
        arm.assertion_ok = all(
            check_assertion(r.text, must_contain, must_match) for r in arm.runs
        )
    return arm


def build_result(
    baseline: Arm,
    candidate: Arm,
    *,
    assertion_declared: bool,
    notes: list[str],
) -> dict[str, Any]:
    saved_tokens = baseline.tokens - candidate.tokens
    saved_bytes = baseline.bytes_len - candidate.bytes_len
    # A zero-token baseline has no denominator. Reporting 0.0% would state "no
    # change" for what may be a total regression, so leave the ratio undefined.
    pct = (saved_tokens / baseline.tokens * 100.0) if baseline.tokens else None

    problems: list[str] = []
    if pct is None:
        problems.append(
            "the baseline produced no output, so there is no denominator and no "
            "percentage can be computed; choose a baseline that does the work"
        )
    if not assertion_declared:
        problems.append(
            "no preserved-answer assertion was declared, so a smaller output "
            "cannot be distinguished from a lost answer"
        )
    else:
        if candidate.assertion_ok is False:
            problems.append(
                "the candidate output failed the preserved-answer assertion; its "
                "output is smaller because information is missing"
            )
        if baseline.assertion_ok is False:
            problems.append(
                "the baseline output failed the preserved-answer assertion, so the "
                "assertion does not describe this task"
            )
    if baseline.exit_codes and candidate.exit_codes:
        if set(baseline.exit_codes) != set(candidate.exit_codes):
            problems.append(
                f"arms disagree on exit status (baseline {baseline.exit_codes}, "
                f"candidate {candidate.exit_codes}); they may not be doing the same work"
            )
    if not baseline.deterministic or not candidate.deterministic:
        notes.append(
            "output varied between runs; the median-length run was measured and the "
            "percentage should be treated as approximate"
        )
    if baseline.counting != candidate.counting:  # pragma: no cover - defensive
        problems.append(
            "arms were counted with different tokenizers and are not comparable"
        )
    for arm in (baseline, candidate):
        if arm.truncated:
            problems.append(
                f"the {arm.label} arm exceeded the capture limit and was stopped, so its "
                "size is a floor rather than a measurement"
            )

    if problems:
        verdict = "unverified"
    elif abs(pct) < MATERIALITY_THRESHOLD_PCT:
        verdict = "inconclusive"
    elif pct > 0:
        verdict = "saves"
    else:
        verdict = "costs"

    # On an invalid comparison the difference is a raw size delta, not a saving.
    # Emitting it under `saved_*` lets a reader or a script quote the number this
    # tool just refused to stand behind, so those keys are null and the raw
    # values move to differently named fields.
    quotable = verdict != "unverified"
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "counting": baseline.counting,
        "attribution": "controlled",
        "saved_tokens": saved_tokens if quotable else None,
        "saved_bytes": saved_bytes if quotable else None,
        "saved_pct": (round(pct, 2) if pct is not None else None) if quotable else None,
        "size_delta_tokens": saved_tokens,
        "size_delta_bytes": saved_bytes,
        "size_delta_pct": round(pct, 2) if pct is not None else None,
        "materiality_threshold_pct": MATERIALITY_THRESHOLD_PCT,
        "baseline": baseline.as_dict(),
        "candidate": candidate.as_dict(),
        "problems": problems,
        "notes": notes,
    }


def render_text(result: dict[str, Any]) -> str:
    base = result["baseline"]
    cand = result["candidate"]
    pct = result["size_delta_pct"]
    delta = f"{result['size_delta_tokens']:,} tokens"
    delta += f" ({pct:+.2f}%)" if pct is not None else " (percentage undefined)"
    label = "delta" if result["verdict"] != "unverified" else "size diff"
    lines = [
        f"verdict: {result['verdict'].upper()}",
        f"counting: {result['counting']} | attribution: {result['attribution']}",
        "",
        f"baseline   {base['command']}",
        f"           {base['tokens']:,} tokens / {base['bytes']:,} bytes "
        f"/ {base['median_duration_s']}s",
        f"candidate  {cand['command']}",
        f"           {cand['tokens']:,} tokens / {cand['bytes']:,} bytes "
        f"/ {cand['median_duration_s']}s",
        "",
        f"{label:<10} {delta}",
    ]
    if result["verdict"] == "unverified":
        lines.append(
            "           this is a raw size difference, not a savings result; "
            "it must not be quoted"
        )
    if result["verdict"] == "inconclusive":
        lines.append(
            f"           below the {result['materiality_threshold_pct']:g}% materiality "
            "threshold; not reportable as a win"
        )
    for problem in result["problems"]:
        lines.append(f"problem:   {problem}")
    for note in result["notes"]:
        lines.append(f"note:      {note}")
    if result["verdict"] == "saves":
        lines.append("")
        lines.append(
            "This result is causal for this command on this corpus. It does not "
            "generalize to other corpora without re-measurement."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure whether a candidate command really reduces tokens."
    )
    parser.add_argument("--baseline", required=True, help="command an agent runs today")
    parser.add_argument(
        "--candidate", required=True, help="command claimed to be cheaper"
    )
    parser.add_argument(
        "--must-contain",
        action="append",
        default=[],
        metavar="TEXT",
        help="substring both arms must still emit; repeatable",
    )
    parser.add_argument(
        "--must-match",
        action="append",
        default=[],
        metavar="REGEX",
        help="regex both arms must still match; repeatable",
    )
    parser.add_argument(
        "--no-assertion",
        action="store_true",
        help="run without a preserved-answer assertion and accept an unverified verdict",
    )
    parser.add_argument("--runs", type=int, default=3, help="runs per arm (default 3)")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="per-run timeout in seconds"
    )
    parser.add_argument(
        "--max-capture-bytes",
        type=int,
        default=DEFAULT_MAX_CAPTURE_BYTES,
        help="stop an arm that emits more than this many bytes (default 64 MiB)",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="interpret commands with the shell; needed for pipes and redirection",
    )
    parser.add_argument(
        "--tokenizer",
        metavar="ENCODING",
        help="tiktoken encoding to use, e.g. o200k_base. Valid only for OpenAI-family "
        "models; no offline tokenizer exists for Claude.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if args.runs < 1:
        print("error: --runs must be at least 1", file=sys.stderr)
        return 2

    # An empty needle matches everything, so it would satisfy the gate without
    # asserting anything. Drop empties, then judge what is actually left.
    raw_contain = list(args.must_contain)
    raw_match = list(args.must_match)
    must_contain = [s for s in raw_contain if s]
    match_sources = [s for s in raw_match if s]
    if (raw_contain or raw_match) and not (must_contain or match_sources):
        print(
            "error: every assertion was empty, and an empty assertion matches any "
            "output; give a substring or pattern the answer must still contain",
            file=sys.stderr,
        )
        return 2

    try:
        must_match = [re.compile(pattern) for pattern in match_sources]
    except re.error as exc:
        # Compile before running either arm: an unusable pattern is a setup
        # error, and reporting it as `unverified` would misuse that verdict.
        print(f"error: invalid --must-match pattern: {exc}", file=sys.stderr)
        return 2

    assertion_declared = bool(must_contain or must_match)
    if not assertion_declared and not args.no_assertion:
        print(
            "error: declare --must-contain/--must-match so a smaller output can be "
            "told apart from a lost answer, or pass --no-assertion to accept an "
            "unverified verdict",
            file=sys.stderr,
        )
        return 2

    encoder, notes = load_encoder(args.tokenizer)
    if not args.tokenizer:
        notes.append(
            "token counts are heuristic; Anthropic publishes no offline tokenizer, "
            "so treat the percentage as an estimate of relative size"
        )

    try:
        baseline = measure(
            "baseline",
            args.baseline,
            runs=args.runs,
            use_shell=args.shell,
            timeout=args.timeout,
            encoder=encoder,
            must_contain=must_contain,
            must_match=must_match,
            max_bytes=args.max_capture_bytes,
        )
        candidate = measure(
            "candidate",
            args.candidate,
            runs=args.runs,
            use_shell=args.shell,
            timeout=args.timeout,
            encoder=encoder,
            must_contain=must_contain,
            must_match=must_match,
            max_bytes=args.max_capture_bytes,
        )
    except BenchmarkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = build_result(
        baseline, candidate, assertion_declared=assertion_declared, notes=notes
    )

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result), end="")

    # Only a verified, material saving is a success. Anything else must not be
    # quotable as one.
    return 0 if result["verdict"] in ("saves", "costs", "inconclusive") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
