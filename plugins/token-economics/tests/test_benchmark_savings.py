#!/usr/bin/env python3
"""Tests for benchmark_savings.py, focused on refusing unearned claims."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benchmark_savings as bs  # noqa: E402


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
        self.assertEqual(result["saved_pct"], 100.0)
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
        self.assertTrue(any("does not describe this task" in p for p in result["problems"]))

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
        self.assertEqual(result["saved_tokens"], -5000)
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
    def test_heuristic_counting_is_graded_estimated(self) -> None:
        tokens, grade = bs.count_tokens("x" * 400, None)
        self.assertEqual(grade, "estimated")
        self.assertEqual(tokens, 100)

    def test_encoder_result_is_graded_by_tokenizer(self) -> None:
        class FakeEncoder:
            def encode(self, text: str, disallowed_special=()):  # noqa: ANN001
                return text.split()

        tokens, grade = bs.count_tokens("a b c", FakeEncoder())
        self.assertEqual((tokens, grade), (3, "tiktoken"))

    def test_encoder_failure_falls_back_to_heuristic(self) -> None:
        class BrokenEncoder:
            def encode(self, text: str, disallowed_special=()):  # noqa: ANN001
                raise RuntimeError("boom")

        tokens, grade = bs.count_tokens("x" * 8, BrokenEncoder())
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
        cmd = f"{sys.executable} -c \"import time; print(time.time_ns())\""
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


class CliTest(unittest.TestCase):
    def test_missing_assertion_is_rejected_before_running(self) -> None:
        code = bs.main(["--baseline", "true", "--candidate", "true"])
        self.assertEqual(code, 2)

    def test_no_assertion_optout_runs_but_cannot_pass(self) -> None:
        code = bs.main(
            ["--baseline", "true", "--candidate", "true", "--no-assertion", "--runs", "1"]
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
            ["--baseline", "true", "--candidate", "true", "--must-match", "(", "--runs", "1"]
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
            ["--baseline", "true", "--candidate", "true", "--no-assertion", "--runs", "0"]
        )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
