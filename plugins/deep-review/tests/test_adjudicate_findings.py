from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "adjudicate-findings.py"
SPEC = importlib.util.spec_from_file_location("adjudicate_findings", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
adjudicate_findings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adjudicate_findings)


def report(lens: str, findings: str, *, reviewed: list[str] | None = None) -> str:
    scope = json.dumps(reviewed if reviewed is not None else ["src/pay/refund.ts"])
    return (
        "---\n"
        "schema: context-kit/review-findings-v1\n"
        f"lens: {lens}\n"
        "artifact: repo@abc123\n"
        f"scope_reviewed: {scope}\n"
        "scope_skipped: []\n"
        "---\n\n"
        "## Summary\n\nA summary.\n\n"
        "## Findings\n\n"
        f"{findings}\n\n"
        "## Coverage\n\nRead the diff.\n"
    )


DEFECT = (
    "- [DEFECT] [severity: major] `src/pay/refund.ts:118`\n"
    "  **Problem:** refund amount is not clamped to the captured total.\n"
    "  **Consequence:** a caller can refund more than was captured, losing money.\n"
    "  **Falsification:** call refund with amount greater than the capture.\n"
    "  **Resolution:** clamp the refund amount against the capture record.\n"
)


class Harness(unittest.TestCase):
    def run_cli(self, reports: dict[str, str], frame: dict | None = None, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        findings = root / "findings"
        findings.mkdir()
        for name, text in reports.items():
            (findings / f"{name}.md").write_text(text, encoding="utf-8")
        frame_data = (
            frame
            if frame is not None
            else {
                "schema": "context-kit/review-frame-v1",
                "artifact": "repo@abc123",
                "decision": "merge",
                "stakes": "payment correctness",
                "expected_lenses": sorted(reports),
            }
        )
        frame_path = root / "frame.json"
        frame_path.write_text(json.dumps(frame_data), encoding="utf-8")
        out = root / "report"
        argv = [
            "--frame",
            str(frame_path),
            "--findings-dir",
            str(findings),
            "--out-dir",
            str(out),
        ]
        for key, value in kwargs.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        code = adjudicate_findings.main(argv)
        ledger = None
        if (out / "ledger.json").exists():
            ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
        return code, ledger, out


class TestParsing(unittest.TestCase):
    def test_parses_finding_fields_including_continuations(self) -> None:
        findings, unparsed, _stray = adjudicate_findings.parse_findings_section(
            [
                "- [RISK] [severity: minor] `a.py:1`",
                "  **Problem:** something",
                "    that wraps onto a second line.",
                "  **Consequence:** slow.",
                "  **Trigger:** high load.",
                "  **Resolution:** batch it.",
            ]
        )
        self.assertEqual(unparsed, 0)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["fields"]["problem"], "something that wraps onto a second line."
        )
        self.assertEqual(findings[0]["type"], "RISK")

    def test_counts_bullets_that_miss_the_contract(self) -> None:
        _, unparsed, _stray = adjudicate_findings.parse_findings_section(
            ["- [DEFECT] missing the severity block and citation"]
        )
        self.assertEqual(unparsed, 1)

    def test_citation_normalizes_backticks_and_whitespace(self) -> None:
        self.assertEqual(
            adjudicate_findings.normalize_citation("  `src/a.ts:10`  "), "src/a.ts:10"
        )


class TestContract(Harness):
    def test_clean_panel_passes(self) -> None:
        code, ledger, out = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "architect": report(
                    "architect",
                    "- [JUDGMENT] [severity: minor] `src/pay/refund.ts:12`\n"
                    "  **Problem:** helper duplicates the ledger module.\n"
                    "  **Consequence:** two places to change on a pricing update.\n"
                    "  **Resolution:** reuse the ledger helper.\n",
                ),
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 2)
        self.assertTrue((out / "review.md").exists())

    def test_defect_without_falsification_fails(self) -> None:
        broken = (
            "- [DEFECT] [severity: blocking] `src/a.ts:1`\n"
            "  **Problem:** it is wrong.\n"
            "  **Consequence:** bad things.\n"
            "  **Resolution:** fix it.\n"
        )
        code, _, _ = self.run_cli({"adversarial": report("adversarial", broken)})
        self.assertEqual(code, 1)

    def test_risk_without_trigger_fails(self) -> None:
        broken = (
            "- [RISK] [severity: minor] `src/a.ts:1`\n"
            "  **Problem:** may be slow.\n"
            "  **Consequence:** latency.\n"
            "  **Resolution:** measure it.\n"
        )
        code, _, _ = self.run_cli({"operator": report("operator", broken)})
        self.assertEqual(code, 1)

    def test_missing_section_is_a_failed_lens(self) -> None:
        truncated = (
            "---\nschema: context-kit/review-findings-v1\nlens: consumer\n"
            "artifact: repo@abc123\nscope_reviewed: []\nscope_skipped: []\n---\n\n"
            "## Summary\n\nA summary.\n\n## Findings\n\nNone.\n"
        )
        code, _, _ = self.run_cli({"consumer": truncated})
        self.assertEqual(code, 1)

    def test_unknown_type_is_rejected(self) -> None:
        bogus = "- [NITPICK] [severity: note] `src/a.ts:1`\n" "  **Problem:** naming.\n"
        code, ledger, _ = self.run_cli({"consumer": report("consumer", bogus)})
        self.assertEqual(code, 1)
        # Rejected findings are counted, not merged: an unfalsified defect must
        # never reach the ledger's findings list.
        self.assertEqual(ledger["counts"]["rejected_findings"], 1)
        self.assertEqual(ledger["counts"]["merged_findings"], 0)

    def test_zero_findings_is_a_clean_result(self) -> None:
        code, ledger, _ = self.run_cli({"consumer": report("consumer", "None.")})
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 0)


class TestRosterHonesty(Harness):
    def test_missing_declared_lens_fails_and_is_named(self) -> None:
        frame = {
            "schema": "context-kit/review-frame-v1",
            "artifact": "repo@abc123",
            "decision": "merge",
            "stakes": "payment correctness",
            "expected_lenses": ["adversarial", "operator"],
        }
        code, ledger, out = self.run_cli(
            {"adversarial": report("adversarial", DEFECT)}, frame=frame
        )
        self.assertEqual(code, 1)
        self.assertEqual(ledger["lenses"]["missing"], ["operator"])
        self.assertIn(
            "Degraded review", (out / "review.md").read_text(encoding="utf-8")
        )

    def test_undeclared_lens_fails(self) -> None:
        frame = {
            "schema": "context-kit/review-frame-v1",
            "artifact": "repo@abc123",
            "decision": "merge",
            "stakes": "x",
            "expected_lenses": ["adversarial"],
        }
        code, ledger, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "consumer": report("consumer", "None."),
            },
            frame=frame,
        )
        self.assertEqual(code, 1)
        self.assertEqual(ledger["lenses"]["undeclared"], ["consumer"])

    def test_empty_roster_is_rejected(self) -> None:
        frame = {
            "schema": "context-kit/review-frame-v1",
            "artifact": "repo@abc123",
            "decision": "merge",
            "stakes": "x",
            "expected_lenses": [],
        }
        code, _, _ = self.run_cli(
            {"adversarial": report("adversarial", DEFECT)}, frame=frame
        )
        self.assertEqual(code, 1)

    def test_duplicate_lens_reports_fail(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        findings = root / "findings"
        findings.mkdir()
        (findings / "a.md").write_text(report("adversarial", DEFECT), encoding="utf-8")
        (findings / "b.md").write_text(report("adversarial", DEFECT), encoding="utf-8")
        frame = root / "frame.json"
        frame.write_text(
            json.dumps(
                {
                    "schema": "context-kit/review-frame-v1",
                    "expected_lenses": ["adversarial"],
                }
            ),
            encoding="utf-8",
        )
        code = adjudicate_findings.main(
            [
                "--frame",
                str(frame),
                "--findings-dir",
                str(findings),
                "--out-dir",
                str(root / "report"),
            ]
        )
        self.assertEqual(code, 1)


class TestCorroboration(Harness):
    def test_same_finding_from_two_lenses_merges_once(self) -> None:
        echo = (
            "- [DEFECT] [severity: blocking] `src/pay/refund.ts:118`\n"
            "  **Problem:** refund amount is not clamped to the captured total.\n"
            "  **Consequence:** refunds can exceed the capture.\n"
            "  **Falsification:** refund above the capture amount.\n"
            "  **Resolution:** clamp the refund amount against the capture record.\n"
        )
        code, ledger, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": report("operator", echo),
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 1)
        self.assertEqual(ledger["counts"]["raw_findings"], 2)
        entry = ledger["findings"][0]
        self.assertTrue(entry["corroborated"])
        self.assertEqual(entry["lenses"], ["adversarial", "operator"])
        # Highest asserted severity wins; averaging would dilute `blocking`.
        self.assertEqual(entry["severity"], "blocking")

    def test_different_problems_at_one_citation_stay_separate(self) -> None:
        other = (
            "- [DEFECT] [severity: minor] `src/pay/refund.ts:118`\n"
            "  **Problem:** currency code is ignored when building the receipt.\n"
            "  **Consequence:** receipts show the wrong symbol abroad.\n"
            "  **Falsification:** issue a refund on a EUR capture.\n"
            "  **Resolution:** thread the currency through the receipt builder.\n"
        )
        code, ledger, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "consumer": report("consumer", other),
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 2)
        self.assertEqual(ledger["counts"]["corroborated"], 0)

    def test_merge_is_order_independent(self) -> None:
        echo = DEFECT.replace("[severity: major]", "[severity: minor]")
        first, _, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": report("operator", echo),
            }
        )
        second, ledger_b, _ = self.run_cli(
            {
                "operator": report("operator", echo),
                "adversarial": report("adversarial", DEFECT),
            }
        )
        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(ledger_b["counts"]["merged_findings"], 1)
        self.assertEqual(ledger_b["findings"][0]["lenses"], ["adversarial", "operator"])

    def test_same_lens_twice_is_not_corroboration(self) -> None:
        doubled = DEFECT + DEFECT.replace("major", "minor")
        code, ledger, _ = self.run_cli({"adversarial": report("adversarial", doubled)})
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 1)
        self.assertFalse(ledger["findings"][0]["corroborated"])


class TestTradeoffs(Harness):
    def test_conflicting_resolutions_surface_as_a_candidate(self) -> None:
        architect = (
            "- [JUDGMENT] [severity: minor] `src/pay/refund.ts:40`\n"
            "  **Problem:** the refund path bypasses the ledger abstraction.\n"
            "  **Consequence:** future ledger changes must patch two call sites.\n"
            "  **Resolution:** introduce a RefundLedger interface and route through it.\n"
        )
        consumer = (
            "- [JUDGMENT] [severity: minor] `src/pay/refund.ts:40`\n"
            "  **Problem:** callers must construct three objects for one refund.\n"
            "  **Consequence:** the common path needs boilerplate nobody remembers.\n"
            "  **Resolution:** delete indirection and expose one flat function.\n"
        )
        code, ledger, out = self.run_cli(
            {
                "architect": report("architect", architect),
                "consumer": report("consumer", consumer),
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(ledger["tradeoff_candidates"]), 1)
        candidate = ledger["tradeoff_candidates"][0]
        self.assertEqual(candidate["citation"], "src/pay/refund.ts:40")
        self.assertEqual(len(candidate["positions"]), 2)
        text = (out / "review.md").read_text(encoding="utf-8")
        self.assertIn("Owner decision required", text)

    def test_agreeing_lenses_do_not_produce_a_tradeoff(self) -> None:
        echo = (
            "- [DEFECT] [severity: major] `src/pay/refund.ts:118`\n"
            "  **Problem:** refund amount is not clamped to the captured total.\n"
            "  **Consequence:** overpayment.\n"
            "  **Falsification:** refund above capture.\n"
            "  **Resolution:** clamp the refund amount against the capture record.\n"
        )
        _, ledger, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": report("operator", echo),
            }
        )
        self.assertEqual(ledger["tradeoff_candidates"], [])

    def test_one_lens_cannot_disagree_with_itself(self) -> None:
        two = (
            "- [JUDGMENT] [severity: minor] `src/a.ts:1`\n"
            "  **Problem:** alpha concern about module layout.\n"
            "  **Consequence:** confusing layout.\n"
            "  **Resolution:** split the module into two files.\n"
            "- [JUDGMENT] [severity: minor] `src/a.ts:1`\n"
            "  **Problem:** beta concern regarding import cycles.\n"
            "  **Consequence:** cyclic imports.\n"
            "  **Resolution:** merge everything into a single entry point.\n"
        )
        _, ledger, _ = self.run_cli({"architect": report("architect", two)})
        self.assertEqual(ledger["tradeoff_candidates"], [])


class TestRoutingAndOutput(Harness):
    def test_defects_route_to_verify_and_risks_to_runtime(self) -> None:
        risk = (
            "- [RISK] [severity: major] `src/pay/refund.ts:200`\n"
            "  **Problem:** retry storm under downstream timeout.\n"
            "  **Consequence:** duplicate refunds during an outage.\n"
            "  **Trigger:** gateway latency above the client timeout.\n"
            "  **Resolution:** add idempotency keys to the retry path.\n"
        )
        code, ledger, out = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": report("operator", risk),
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(ledger["routing"]["verify"]), 1)
        self.assertEqual(len(ledger["routing"]["risk_triage"]), 1)
        self.assertIn("unverified", (out / "review.md").read_text(encoding="utf-8"))

    def test_coverage_records_skipped_regions(self) -> None:
        text = (
            "---\nschema: context-kit/review-findings-v1\nlens: operator\n"
            "artifact: repo@abc123\n"
            'scope_reviewed: ["src/pay"]\n'
            'scope_skipped: [{"region": "src/legacy", "reason": "out of scope"}]\n'
            "---\n\n## Summary\n\nS.\n\n## Findings\n\nNone.\n\n## Coverage\n\nC.\n"
        )
        code, ledger, out = self.run_cli({"operator": text})
        self.assertEqual(code, 0)
        self.assertEqual(
            ledger["coverage"]["operator"]["skipped"],
            [{"region": "src/legacy", "reason": "out of scope"}],
        )
        self.assertIn("src/legacy", (out / "review.md").read_text(encoding="utf-8"))

    def test_refuses_to_write_into_the_findings_directory(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        findings = root / "findings"
        findings.mkdir()
        (findings / "a.md").write_text(report("adversarial", DEFECT), encoding="utf-8")
        frame = root / "frame.json"
        frame.write_text(
            json.dumps(
                {
                    "schema": "context-kit/review-frame-v1",
                    "expected_lenses": ["adversarial"],
                }
            ),
            encoding="utf-8",
        )
        code = adjudicate_findings.main(
            [
                "--frame",
                str(frame),
                "--findings-dir",
                str(findings),
                "--out-dir",
                str(findings / "report"),
            ]
        )
        self.assertEqual(code, 1)

    def test_wrong_frame_schema_is_rejected(self) -> None:
        code, _, _ = self.run_cli(
            {"adversarial": report("adversarial", DEFECT)},
            frame={
                "schema": "context-kit/other-v1",
                "expected_lenses": ["adversarial"],
            },
        )
        self.assertEqual(code, 1)

    def test_out_of_range_threshold_is_a_usage_error(self) -> None:
        code, _, _ = self.run_cli(
            {"adversarial": report("adversarial", DEFECT)}, merge_threshold=1.5
        )
        self.assertEqual(code, 2)


class TestReviewFeedbackRegressions(Harness):
    """Regressions for defects found in review of the initial implementation."""

    def test_agreement_on_problem_with_opposing_fixes_is_a_tradeoff(self) -> None:
        """The worst failure this plugin could have: two lenses agree on the
        problem, propose opposite fixes, and corroboration swallows the dissent.
        """
        shared_problem = (
            "  **Problem:** the retry loop can double-charge the customer.\n"
            "  **Consequence:** duplicate charges reach the ledger.\n"
            "  **Falsification:** kill the gateway mid-retry.\n"
        )
        adversarial = (
            "- [DEFECT] [severity: major] `src/a.ts:10`\n"
            + shared_problem
            + "  **Resolution:** make the whole charge path idempotent with a stored key.\n"
        )
        architect = (
            "- [DEFECT] [severity: major] `src/a.ts:10`\n"
            + shared_problem
            + "  **Resolution:** delete retries entirely and surface failure to the caller.\n"
        )
        code, ledger, out = self.run_cli(
            {
                "adversarial": report("adversarial", adversarial),
                "architect": report("architect", architect),
            }
        )
        self.assertEqual(code, 0)
        # Still one merged finding: they genuinely agree about the problem.
        self.assertEqual(ledger["counts"]["merged_findings"], 1)
        self.assertTrue(ledger["findings"][0]["corroborated"])
        # But the disagreement about the fix must survive the merge.
        self.assertEqual(len(ledger["tradeoff_candidates"]), 1)
        candidate = ledger["tradeoff_candidates"][0]
        self.assertTrue(candidate["within_finding"])
        resolutions = {p["resolution"] for p in candidate["positions"]}
        self.assertEqual(len(resolutions), 2)
        self.assertIn(
            "same problem, opposing fixes",
            (out / "review.md").read_text(encoding="utf-8"),
        )

    def test_merged_entry_retains_every_lens_resolution(self) -> None:
        echo = (
            "- [DEFECT] [severity: major] `src/pay/refund.ts:118`\n"
            "  **Problem:** refund amount is not clamped to the captured total.\n"
            "  **Consequence:** overpayment.\n"
            "  **Falsification:** refund above capture.\n"
            "  **Resolution:** clamp the refund amount against the capture record.\n"
        )
        _, ledger, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": report("operator", echo),
            }
        )
        positions = ledger["findings"][0]["positions"]
        self.assertEqual(len(positions), 2)
        self.assertEqual(
            sorted(p["lens"] for p in positions), ["adversarial", "operator"]
        )

    def test_stray_prose_in_findings_is_not_a_clean_report(self) -> None:
        code, _, _ = self.run_cli(
            {"consumer": report("consumer", "I ran out of context before finishing.")}
        )
        self.assertEqual(code, 1)

    def test_none_placeholder_is_still_accepted(self) -> None:
        code, ledger, _ = self.run_cli({"consumer": report("consumer", "None.")})
        self.assertEqual(code, 0)
        self.assertEqual(ledger["counts"]["merged_findings"], 0)

    def test_report_from_another_revision_is_rejected(self) -> None:
        stale = report("operator", DEFECT).replace(
            "artifact: repo@abc123", "artifact: repo@deadbee"
        )
        code, _, _ = self.run_cli(
            {
                "adversarial": report("adversarial", DEFECT),
                "operator": stale,
            }
        )
        self.assertEqual(code, 1)

    def test_missing_artifact_is_rejected(self) -> None:
        headless = report("operator", "None.").replace(
            "artifact: repo@abc123\n", "artifact:\n"
        )
        code, _, _ = self.run_cli({"operator": headless})
        self.assertEqual(code, 1)

    def test_malformed_scope_reviewed_is_rejected(self) -> None:
        bad = report("operator", "None.").replace(
            'scope_reviewed: ["src/pay/refund.ts"]', "scope_reviewed: src/"
        )
        code, _, _ = self.run_cli({"operator": bad})
        self.assertEqual(code, 1)

    def test_malformed_scope_skipped_entry_is_rejected(self) -> None:
        bad = report("operator", "None.").replace(
            "scope_skipped: []", 'scope_skipped: ["src/legacy"]'
        )
        code, _, _ = self.run_cli({"operator": bad})
        self.assertEqual(code, 1)

    def test_defect_cited_as_none_is_rejected(self) -> None:
        bad = (
            "- [DEFECT] [severity: blocking] `none`\n"
            "  **Problem:** something is wrong somewhere.\n"
            "  **Consequence:** unclear.\n"
            "  **Falsification:** unclear.\n"
            "  **Resolution:** find it.\n"
        )
        code, ledger, _ = self.run_cli({"adversarial": report("adversarial", bad)})
        self.assertEqual(code, 1)
        # It must not reach verify's queue without a location to look at.
        self.assertEqual(ledger["routing"]["verify"], [])

    def test_question_may_be_cited_as_none(self) -> None:
        ok = (
            "- [QUESTION] [severity: note] `none`\n"
            "  **Problem:** no migration plan appears anywhere in the change.\n"
            "  **Resolution:** point me at the migration plan, or confirm none exists.\n"
        )
        code, ledger, _ = self.run_cli({"architect": report("architect", ok)})
        self.assertEqual(code, 0)
        self.assertEqual(len(ledger["routing"]["answer"]), 1)

    def test_risks_are_queued_for_triage_not_routed(self) -> None:
        """A maintenance risk has a real trigger no command can reproduce, so
        the ledger must not present every risk as runtime-settleable."""
        risk = (
            "- [RISK] [severity: minor] `src/a.ts:1`\n"
            "  **Problem:** this pattern will be costly to evolve.\n"
            "  **Consequence:** future contributors pay a tax on every change.\n"
            "  **Trigger:** the next time a second backend is added.\n"
            "  **Resolution:** extract the backend behind an interface now.\n"
        )
        code, ledger, out = self.run_cli({"architect": report("architect", risk)})
        self.assertEqual(code, 0)
        self.assertNotIn("runtime_evidence", ledger["routing"])
        self.assertEqual(len(ledger["routing"]["risk_triage"]), 1)
        self.assertIn(
            "Risks to triage", (out / "review.md").read_text(encoding="utf-8")
        )


class TestFieldSynthesisGap(Harness):
    """Regressions for a field report where the panel ran but adjudication
    never did, and the resulting hand-written synthesis carried none of this
    plugin's guarantees while looking exactly like one that did."""

    QUESTION_ONLY = (
        "- [QUESTION] [severity: note] `post.md:42`\n"
        "  **Problem:** the cited statistic has no reachable primary source.\n"
        "  **Resolution:** supply the source so the figure can be checked.\n"
    )

    def bundle(self, reports: dict[str, str], frame: dict | None = None):
        """Run with every report concatenated into one file, which is what an
        orchestrator holding inline worker output actually has."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        bundle = root / "findings.md"
        bundle.write_text("\n".join(reports.values()), encoding="utf-8")
        frame_data = (
            frame
            if frame is not None
            else {
                "schema": "context-kit/review-frame-v1",
                "artifact": "repo@abc123",
                "decision": "merge",
                "stakes": "payment correctness",
                "expected_lenses": sorted(reports),
            }
        )
        frame_path = root / "frame.json"
        frame_path.write_text(json.dumps(frame_data), encoding="utf-8")
        out = root / "report"
        code = adjudicate_findings.main(
            [
                "--frame",
                str(frame_path),
                "--findings-file",
                str(bundle),
                "--out-dir",
                str(out),
            ]
        )
        ledger = None
        if (out / "ledger.json").exists():
            ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
        return code, ledger, out

    def test_bundled_reports_adjudicate_like_separate_files(self) -> None:
        reports = {
            "adversarial": report("adversarial", DEFECT),
            "operator": report(
                "operator",
                "- [RISK] [severity: major] `src/pay/gateway.ts:200`\n"
                "  **Problem:** the retry loop has no idempotency key.\n"
                "  **Consequence:** duplicate refunds during an outage.\n"
                "  **Trigger:** gateway latency above the client timeout.\n"
                "  **Resolution:** attach an idempotency key to each attempt.\n",
            ),
        }
        from_dir_code, from_dir, _ = self.run_cli(reports)
        bundled_code, bundled, _ = self.bundle(reports)
        self.assertEqual(from_dir_code, 0)
        self.assertEqual(bundled_code, 0)
        self.assertEqual(bundled["lenses"]["reported"], from_dir["lenses"]["reported"])
        self.assertEqual(bundled["counts"], from_dir["counts"])
        self.assertEqual(bundled["routing"], from_dir["routing"])

    def test_bundle_preserves_a_caller_defined_domain_lens(self) -> None:
        code, ledger, _ = self.bundle(
            {
                "adversarial": report("adversarial", DEFECT),
                "disclosure-risk": report("disclosure-risk", self.QUESTION_ONLY),
            }
        )
        self.assertEqual(code, 0)
        self.assertIn("disclosure-risk", ledger["lenses"]["reported"])

    def test_bundle_with_no_report_is_rejected(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        bundle = root / "findings.md"
        bundle.write_text("Here is my summary of the review.\n", encoding="utf-8")
        frame = root / "frame.json"
        frame.write_text(
            json.dumps(
                {
                    "schema": "context-kit/review-frame-v1",
                    "expected_lenses": ["adversarial"],
                }
            ),
            encoding="utf-8",
        )
        code = adjudicate_findings.main(
            [
                "--frame",
                str(frame),
                "--findings-file",
                str(bundle),
                "--out-dir",
                str(root / "report"),
            ]
        )
        self.assertEqual(code, 1)

    def test_bundle_splitting_ignores_fenced_examples(self) -> None:
        quoting = report(
            "architect",
            "- [JUDGMENT] [severity: note] `docs/contract.md:1`\n"
            "  **Problem:** the contract example is stale.\n"
            "  **Consequence:** workers copy an outdated header.\n"
            "  **Resolution:** refresh the fenced example.\n",
        ).replace(
            "## Coverage\n\nRead the diff.\n",
            "## Coverage\n\nRead the diff. The stale example reads:\n\n"
            "```markdown\n---\nschema: context-kit/review-findings-v1\n"
            "lens: ghost\n---\n```\n",
        )
        code, ledger, _ = self.bundle({"architect": quoting})
        self.assertEqual(code, 0)
        # The fenced sample must not be split out as a second `ghost` lens.
        self.assertEqual(ledger["lenses"]["reported"], ["architect"])

    def test_question_only_lens_is_flagged_not_read_as_clean(self) -> None:
        """The field case: lenses without fetch tools returned only questions,
        and the panel reported zero defects as though nothing was wrong."""
        code, ledger, out = self.run_cli(
            {
                "adversarial": report("adversarial", self.QUESTION_ONLY),
                "consumer": report("consumer", self.QUESTION_ONLY),
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            ledger["lenses"]["question_dominated"], ["adversarial", "consumer"]
        )
        text = (out / "review.md").read_text(encoding="utf-8")
        self.assertIn("Degraded review", text)
        self.assertIn("could not look", text)

    def test_lens_with_no_findings_is_clean_not_question_dominated(self) -> None:
        code, ledger, out = self.run_cli({"consumer": report("consumer", "None.")})
        self.assertEqual(code, 0)
        self.assertEqual(ledger["lenses"]["question_dominated"], [])
        self.assertNotIn(
            "Degraded review", (out / "review.md").read_text(encoding="utf-8")
        )

    def test_lens_that_judged_anything_is_not_flagged(self) -> None:
        mixed = DEFECT + self.QUESTION_ONLY
        _, ledger, _ = self.run_cli({"adversarial": report("adversarial", mixed)})
        self.assertEqual(ledger["lenses"]["question_dominated"], [])

    def test_both_input_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            adjudicate_findings.main(
                [
                    "--frame",
                    "f.json",
                    "--findings-dir",
                    "d",
                    "--findings-file",
                    "b.md",
                    "--out-dir",
                    "o",
                ]
            )

    def test_an_input_source_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            adjudicate_findings.main(["--frame", "f.json", "--out-dir", "o"])


class TestSeverity(unittest.TestCase):
    def test_highest_severity_wins(self) -> None:
        self.assertEqual(
            adjudicate_findings._max_severity(["note", "blocking", "minor"]), "blocking"
        )

    def test_unknown_severity_falls_back_to_lowest(self) -> None:
        self.assertEqual(adjudicate_findings._max_severity(["bogus"]), "note")


if __name__ == "__main__":
    unittest.main()
