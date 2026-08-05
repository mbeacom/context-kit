#!/usr/bin/env python3
"""Tests for benchmark_savings.py, focused on refusing unearned claims."""

from __future__ import annotations

import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benchmark_savings as bs


def arm(
    label: str,
    *,
    tokens: int,
    nbytes: int = 0,
    exit_codes: list[int] | None = None,
    assertion_ok: bool | None = True,
    deterministic: bool = True,
    counting: str = "estimated",
) -> bs.Arm:
    a = bs.Arm(label=label, command=f"{label}-cmd")
    a.tokens = tokens
    a.bytes_len = nbytes or tokens * 4
    a.exit_codes = exit_codes if exit_codes is not None else [0]
    a.assertion_ok = assertion_ok
    a.deterministic = deterministic
    a.counting = counting
    return a


class VerdictTest(unittest.TestCase):
    def test_material_verified_reduction_is_a_saving(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000),
            arm("candidate", tokens=200),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "saves")
        self.assertEqual(result["saved_tokens"], 800)
        self.assertEqual(result["saved_pct"], 80.0)
        self.assertEqual(result["problems"], [])

    def test_missing_assertion_makes_any_reduction_unverified(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000, assertion_ok=None),
            arm("candidate", tokens=0, assertion_ok=None),
            assertion_declared=False,
            notes=[],
        )
        # Discarding all output looks like a perfect saving; it must not pass.
        self.assertEqual(result["verdict"], "unverified")
        # The raw delta stays available, but never under a `saved_*` name.
        self.assertIsNone(result["saved_pct"])
        self.assertIsNone(result["saved_tokens"])
        self.assertEqual(result["size_delta_pct"], 100.0)
        self.assertTrue(any("preserved-answer" in p for p in result["problems"]))

    def test_failed_candidate_assertion_is_unverified(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000, assertion_ok=True),
            arm("candidate", tokens=1, assertion_ok=False),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "unverified")
        self.assertTrue(any("information is missing" in p for p in result["problems"]))

    def test_failed_baseline_assertion_invalidates_the_comparison(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000, assertion_ok=False),
            arm("candidate", tokens=100, assertion_ok=True),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "unverified")
        self.assertTrue(
            any("does not describe this task" in p for p in result["problems"])
        )

    def test_divergent_exit_codes_invalidate_the_comparison(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000, exit_codes=[0]),
            arm("candidate", tokens=100, exit_codes=[1]),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "unverified")
        self.assertTrue(any("exit status" in p for p in result["problems"]))

    def test_small_reduction_is_inconclusive_not_a_win(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000),
            arm("candidate", tokens=980),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "inconclusive")

    def test_regression_is_reported_as_a_cost(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=100),
            arm("candidate", tokens=500),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "costs")
        self.assertLess(result["saved_pct"], 0)

    def test_nondeterministic_output_is_disclosed_but_still_verdicted(self) -> None:
        notes: list[str] = []
        result = bs.build_result(
            arm("baseline", tokens=1000, deterministic=False),
            arm("candidate", tokens=100),
            assertion_declared=True,
            notes=notes,
        )
        self.assertEqual(result["verdict"], "saves")
        self.assertTrue(any("varied between runs" in n for n in result["notes"]))

    def test_mixed_tokenizers_are_not_comparable(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=1000, counting="estimated"),
            arm("candidate", tokens=100, counting="tiktoken"),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["verdict"], "unverified")

    def test_attribution_is_always_controlled_for_ab_runs(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=10),
            arm("candidate", tokens=10),
            assertion_declared=True,
            notes=[],
        )
        self.assertEqual(result["attribution"], "controlled")

    def test_zero_token_baseline_has_no_percentage_and_is_unverified(self) -> None:
        # A silent 0.0% here would report a total regression as "no change".
        result = bs.build_result(
            arm("baseline", tokens=0),
            arm("candidate", tokens=5000),
            assertion_declared=True,
            notes=[],
        )
        self.assertIsNone(result["saved_pct"])
        self.assertEqual(result["verdict"], "unverified")
        self.assertEqual(result["size_delta_tokens"], -5000)
        self.assertTrue(any("no denominator" in p for p in result["problems"]))

    def test_zero_token_baseline_is_unverified_even_when_both_are_empty(self) -> None:
        result = bs.build_result(
            arm("baseline", tokens=0),
            arm("candidate", tokens=0),
            assertion_declared=True,
            notes=[],
        )
        self.assertIsNone(result["saved_pct"])
        self.assertEqual(result["verdict"], "unverified")


class AssertionCheckTest(unittest.TestCase):
    def test_all_substrings_must_be_present(self) -> None:
        self.assertTrue(bs.check_assertion("alpha beta", ["alpha", "beta"], []))
        self.assertFalse(bs.check_assertion("alpha", ["alpha", "beta"], []))

    def test_regex_assertions_are_applied(self) -> None:
        pattern = [re.compile(r"\d+ errors")]
        self.assertTrue(bs.check_assertion("found 12 errors", [], pattern))
        self.assertFalse(bs.check_assertion("all clear", [], pattern))


class TokenCountTest(unittest.TestCase):
    def test_non_empty_output_never_counts_as_zero_tokens(self) -> None:
        # Rounding alone sent 1-2 bytes to zero, which downstream reported as
        # "the baseline produced no output" about output that exists.
        for size in (1, 2, 3):
            tokens, _ = bs.count_tokens(b"x" * size, None)
            self.assertGreaterEqual(tokens, 1, f"{size} bytes counted as zero")

    def test_only_genuinely_empty_output_counts_as_zero(self) -> None:
        self.assertEqual(bs.count_tokens(b"", None)[0], 0)

    def test_a_tiny_baseline_still_yields_a_comparison(self) -> None:
        baseline = arm("baseline", tokens=bs.count_tokens(b"ok", None)[0])
        candidate = arm("candidate", tokens=bs.count_tokens(b"x" * 400, None)[0])
        result = bs.build_result(baseline, candidate, assertion_declared=True, notes=[])
        self.assertFalse(any("no denominator" in p for p in result["problems"]))
        self.assertEqual(result["verdict"], "costs")

    def test_heuristic_counting_is_graded_estimated(self) -> None:
        tokens, grade = bs.count_tokens(b"x" * 400, None)
        self.assertEqual(grade, "estimated")
        self.assertEqual(tokens, 100)

    def test_heuristic_counts_utf8_bytes_not_code_points(self) -> None:
        # A 4-byte glyph costs four bytes and several real tokens. Counting
        # code points scored it as a quarter token, which inverted verdicts
        # whenever a candidate traded ASCII for symbols.
        ascii_tokens, _ = bs.count_tokens(b"a" * 400, None)
        emoji_tokens, _ = bs.count_tokens("\U0001f600".encode() * 200, None)
        self.assertEqual(ascii_tokens, 100)
        self.assertEqual(emoji_tokens, 200)
        self.assertGreater(emoji_tokens, ascii_tokens)

    def test_encoder_result_is_graded_by_tokenizer(self) -> None:
        class FakeEncoder:
            def encode(self, text: str, disallowed_special=()):
                return text.split()

        tokens, grade = bs.count_tokens(b"a b c", FakeEncoder())
        self.assertEqual((tokens, grade), (3, "tiktoken"))

    def test_encoder_failure_falls_back_to_heuristic(self) -> None:
        class BrokenEncoder:
            def encode(self, text: str, disallowed_special=()):
                raise RuntimeError("boom")

        tokens, grade = bs.count_tokens(b"x" * 8, BrokenEncoder())
        self.assertEqual(grade, "estimated")
        self.assertEqual(tokens, 2)


class ExecutionTest(unittest.TestCase):
    def test_stderr_counts_toward_what_the_agent_reads(self) -> None:
        run = bs.execute(
            f"{sys.executable} -c \"import sys; sys.stderr.write('noisy')\"",
            use_shell=False,
            timeout=30,
        )
        self.assertIn("noisy", run.text)

    def test_missing_binary_raises_benchmark_error(self) -> None:
        with self.assertRaises(bs.BenchmarkError):
            bs.execute("definitely-not-a-real-binary-xyz", use_shell=False, timeout=5)

    def test_empty_command_raises_benchmark_error(self) -> None:
        with self.assertRaises(bs.BenchmarkError):
            bs.execute("   ", use_shell=False, timeout=5)

    def test_measure_detects_nondeterminism(self) -> None:
        cmd = f'{sys.executable} -c "import time; print(time.time_ns())"'
        result = bs.measure(
            "baseline",
            cmd,
            runs=2,
            use_shell=False,
            timeout=30,
            encoder=None,
            must_contain=[],
            must_match=[],
        )
        self.assertFalse(result.deterministic)


class CaptureBoundTest(unittest.TestCase):
    def test_output_past_the_cap_is_stopped_and_flagged(self) -> None:
        run = bs.execute(
            f"{sys.executable} -c \"print('x'*2000000)\"",
            use_shell=False,
            timeout=60,
            max_bytes=50_000,
        )
        self.assertTrue(run.truncated)
        self.assertLessEqual(len(run.data), 50_000 + 65536)

    def test_truncated_arm_cannot_produce_a_saving(self) -> None:
        baseline = arm("baseline", tokens=1000)
        candidate = arm("candidate", tokens=10)
        candidate.truncated = True
        result = bs.build_result(baseline, candidate, assertion_declared=True, notes=[])
        self.assertEqual(result["verdict"], "unverified")
        self.assertTrue(any("capture limit" in p for p in result["problems"]))

    def test_timeout_is_enforced_while_blocked_on_a_quiet_command(self) -> None:
        # The arm writes one line then sleeps, so the reader blocks. A deadline
        # checked only between reads would never fire here.
        started = time.monotonic()
        with self.assertRaises(bs.BenchmarkError):
            bs.execute(
                f"{sys.executable} -c \"import sys,time; sys.stdout.write('hi\\n'); "
                'sys.stdout.flush(); time.sleep(30)"',
                use_shell=False,
                timeout=2,
            )
        self.assertLess(time.monotonic() - started, 15)


class CliTest(unittest.TestCase):
    def test_missing_assertion_is_rejected_before_running(self) -> None:
        code = bs.main(["--baseline", "true", "--candidate", "true"])
        self.assertEqual(code, 2)

    def test_no_assertion_optout_runs_but_cannot_pass(self) -> None:
        code = bs.main(
            [
                "--baseline",
                "true",
                "--candidate",
                "true",
                "--no-assertion",
                "--runs",
                "1",
            ]
        )
        self.assertEqual(code, 1)

    def test_empty_assertion_cannot_satisfy_the_gate(self) -> None:
        # "" is in every string, so this would bless any reduction.
        code = bs.main(
            [
                "--baseline",
                f"{sys.executable} -c \"print('x'*4000)\"",
                "--candidate",
                f"{sys.executable} -c \"print('x'*10)\"",
                "--must-contain",
                "",
                "--runs",
                "1",
            ]
        )
        self.assertEqual(code, 2)

    def test_invalid_regex_is_a_setup_error_not_an_unverified_verdict(self) -> None:
        code = bs.main(
            [
                "--baseline",
                "true",
                "--candidate",
                "true",
                "--must-match",
                "(",
                "--runs",
                "1",
            ]
        )
        self.assertEqual(code, 2)

    def test_unparseable_command_is_a_setup_error(self) -> None:
        code = bs.main(
            [
                "--baseline",
                'echo "unterminated',
                "--candidate",
                "true",
                "--no-assertion",
                "--runs",
                "1",
            ]
        )
        self.assertEqual(code, 2)

    def test_non_executable_target_is_a_setup_error(self) -> None:
        code = bs.main(
            [
                "--baseline",
                tempfile.gettempdir(),
                "--candidate",
                "true",
                "--no-assertion",
                "--runs",
                "1",
            ]
        )
        self.assertEqual(code, 2)

    def test_invalid_run_count_is_rejected(self) -> None:
        code = bs.main(
            [
                "--baseline",
                "true",
                "--candidate",
                "true",
                "--no-assertion",
                "--runs",
                "0",
            ]
        )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
