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
import re
import shlex
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "context-kit/token-savings-v1"

# Widely cited average for English text; source code trends denser. Used only
# when no tokenizer is installed, and always reported as `estimated`.
DEFAULT_BYTES_PER_TOKEN = 4.0

# A savings claim below this magnitude is within the noise of prompt phrasing
# and corpus choice, so it is reported as inconclusive rather than as a win.
MATERIALITY_THRESHOLD_PCT = 5.0


class BenchmarkError(RuntimeError):
    """The benchmark could not produce a comparable pair of arms."""


def count_tokens(text: str, encoder: Any | None) -> tuple[int, str]:
    """Return ``(tokens, grade)`` for ``text``."""
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=())), "tiktoken"
        except Exception:  # pragma: no cover - defensive, encoder is optional
            pass
    return int(round(len(text) / DEFAULT_BYTES_PER_TOKEN)), "estimated"


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
        notes.append(f"tiktoken encoding {name!r} unavailable ({exc}); using the heuristic")
        return None, notes


@dataclass
class Run:
    exit_code: int
    text: str
    duration_s: float


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
        }


def execute(command: str, use_shell: bool, timeout: float) -> Run:
    """Run one command and capture everything an agent would read."""
    started = time.monotonic()
    try:
        if use_shell:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        else:
            argv = shlex.split(command)
            if not argv:
                raise BenchmarkError(f"empty command: {command!r}")
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
    except subprocess.TimeoutExpired as exc:
        raise BenchmarkError(f"command timed out after {timeout}s: {command}") from exc
    except FileNotFoundError as exc:
        raise BenchmarkError(
            f"command not found: {command} ({exc}). Install it or drop this arm."
        ) from exc
    duration = time.monotonic() - started
    # An agent pays for stderr too, so both streams count toward the total.
    return Run(completed.returncode, (completed.stdout or "") + (completed.stderr or ""), duration)


def check_assertion(text: str, must_contain: list[str], must_match: list[str]) -> bool:
    for needle in must_contain:
        if needle not in text:
            return False
    for pattern in must_match:
        if not re.search(pattern, text):
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
    must_match: list[str],
) -> Arm:
    arm = Arm(label=label, command=command)
    for _ in range(runs):
        arm.runs.append(execute(command, use_shell, timeout))
    texts = [r.text for r in arm.runs]
    arm.exit_codes = [r.exit_code for r in arm.runs]
    arm.deterministic = len(set(texts)) == 1
    # With varying output, the median length is the honest representative.
    representative = sorted(texts, key=len)[len(texts) // 2]
    arm.bytes_len = len(representative.encode("utf-8"))
    arm.tokens, arm.counting = count_tokens(representative, encoder)
    if must_contain or must_match:
        arm.assertion_ok = all(check_assertion(t, must_contain, must_match) for t in texts)
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
    pct = (saved_tokens / baseline.tokens * 100.0) if baseline.tokens else 0.0

    problems: list[str] = []
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
        problems.append("arms were counted with different tokenizers and are not comparable")

    if problems:
        verdict = "unverified"
    elif abs(pct) < MATERIALITY_THRESHOLD_PCT:
        verdict = "inconclusive"
    elif pct > 0:
        verdict = "saves"
    else:
        verdict = "costs"

    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "counting": baseline.counting,
        "attribution": "controlled",
        "saved_tokens": saved_tokens,
        "saved_bytes": saved_bytes,
        "saved_pct": round(pct, 2),
        "materiality_threshold_pct": MATERIALITY_THRESHOLD_PCT,
        "baseline": baseline.as_dict(),
        "candidate": candidate.as_dict(),
        "problems": problems,
        "notes": notes,
    }


def render_text(result: dict[str, Any]) -> str:
    base = result["baseline"]
    cand = result["candidate"]
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
        f"delta      {result['saved_tokens']:,} tokens ({result['saved_pct']:+.2f}%)",
    ]
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
    parser.add_argument("--candidate", required=True, help="command claimed to be cheaper")
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

    assertion_declared = bool(args.must_contain or args.must_match)
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
            must_contain=args.must_contain,
            must_match=args.must_match,
        )
        candidate = measure(
            "candidate",
            args.candidate,
            runs=args.runs,
            use_shell=args.shell,
            timeout=args.timeout,
            encoder=encoder,
            must_contain=args.must_contain,
            must_match=args.must_match,
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
