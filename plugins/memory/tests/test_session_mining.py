from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "memory-provider.py"
SPEC = importlib.util.spec_from_file_location("memory_provider_mining", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
memory_provider = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_provider
SPEC.loader.exec_module(memory_provider)


def event(kind: str, **data: object) -> dict[str, object]:
    return {"type": kind, "data": data}


def session_start(session_id: str = "session-1") -> dict[str, object]:
    return event(
        "session.start",
        sessionId=session_id,
        startTime="2026-08-05T10:00:00.000Z",
        producer="copilot-agent",
    )


def log_bytes(events: list[dict[str, object]]) -> bytes:
    return "\n".join(json.dumps(item) for item in events).encode("utf-8")


class CopilotExtractionTests(unittest.TestCase):
    """Attribution rules for GitHub Copilot CLI event logs.

    Copilot records all session activity in one stream, so the risk is not
    missing content but misattributing it. Measured across a real 115-session
    corpus, only 24 of 729 `user.message` events were human-authored.
    """

    def extract(self, events: list[dict[str, object]]):
        return memory_provider._extract_copilot_session(log_bytes(events))

    def test_unrecognized_input_is_not_a_session(self) -> None:
        self.assertIsNone(memory_provider._extract_copilot_session(b"not json"))
        self.assertIsNone(
            memory_provider._extract_copilot_session(
                log_bytes([event("user.message", content="orphaned")])
            )
        )

    def test_session_start_without_an_id_is_not_recognized(self) -> None:
        self.assertIsNone(
            memory_provider._extract_copilot_session(
                log_bytes(
                    [
                        event("session.start", sessionId=""),
                        event("user.message", content="hi"),
                    ]
                )
            )
        )

    def test_recognized_but_empty_session_is_not_none(self) -> None:
        # Distinguishing "recognized and empty" from "unrecognized" is what
        # keeps the caller from falling back to raw event JSON.
        result = self.extract([session_start()])
        self.assertIsNotNone(result)
        self.assertEqual([], result["turns"])

    def test_human_turns_are_kept(self) -> None:
        result = self.extract(
            [
                session_start(),
                event("user.message", content="Why is the deploy failing?"),
                event("assistant.message", content="Checking the workflow."),
            ]
        )
        self.assertEqual(
            [
                {"role": "user", "content": "Why is the deploy failing?"},
                {"role": "assistant", "content": "Checking the workflow."},
            ],
            result["turns"],
        )

    def test_subagent_task_prompts_are_not_human_turns(self) -> None:
        # The orchestrating model writes these, not the person. This is the
        # single largest source of misattribution in the corpus (611 of 729).
        result = self.extract(
            [
                session_start(),
                event("user.message", content="task prompt", parentAgentTaskId="t-1"),
            ]
        )
        self.assertEqual([], result["turns"])
        self.assertEqual(1, result["dropped"]["user_subagent_prompt"])

    def test_every_sourced_user_message_is_generated_context(self) -> None:
        # All 42 distinct `source` values observed in the corpus were
        # generated. The presence of the field is the signal, not a prefix.
        for source in (
            "skill-review-pr",
            "agent-0b45bd8b",
            "command-2b653dd0",
            "system",
        ):
            with self.subTest(source=source):
                result = self.extract(
                    [
                        session_start(),
                        event("user.message", content="generated", source=source),
                    ]
                )
                self.assertEqual([], result["turns"])
                self.assertEqual(1, result["dropped"]["user_generated_context"])

    def test_tool_nested_assistant_messages_are_dropped(self) -> None:
        result = self.extract(
            [
                session_start(),
                event("assistant.message", content="nested", parentToolCallId="c-1"),
                event("assistant.message", content="subagent", parentAgentTaskId="t-1"),
            ]
        )
        self.assertEqual([], result["turns"])
        self.assertEqual(1, result["dropped"]["assistant_tool_nested"])
        self.assertEqual(1, result["dropped"]["assistant_subagent"])

    def test_reasoning_is_never_extracted(self) -> None:
        result = self.extract(
            [
                session_start(),
                event(
                    "assistant.message",
                    content="visible",
                    reasoningText="hidden reasoning",
                    reasoningOpaque="opaque blob",
                ),
            ]
        )
        serialized = json.dumps(result)
        self.assertIn("visible", serialized)
        self.assertNotIn("hidden reasoning", serialized)
        self.assertNotIn("opaque blob", serialized)

    def test_original_content_is_preferred_over_transformed(self) -> None:
        # `content` is what the person wrote; `transformedContent` is
        # post-expansion and differed in 262 of 263 sampled cases.
        result = self.extract(
            [
                session_start(),
                event(
                    "user.message",
                    content="what I typed",
                    transformedContent="what the host expanded",
                ),
            ]
        )
        self.assertEqual("what I typed", result["turns"][0]["content"])

    def test_non_conversational_events_are_excluded(self) -> None:
        result = self.extract(
            [
                session_start(),
                event("tool.execution_start", name="bash"),
                event("hook.start"),
                event("system.message", content="system note"),
                event("session.plan_changed"),
            ]
        )
        self.assertEqual([], result["turns"])
        self.assertEqual(4, result["dropped"]["non_conversational_event"])

    def test_unparsable_lines_are_counted_not_fatal(self) -> None:
        raw = log_bytes([session_start()]) + b"\n{ broken json\n"
        result = memory_provider._extract_copilot_session(raw)
        self.assertEqual(1, result["dropped"]["unparsable_line"])

    def test_attribution_boundary_regression(self) -> None:
        """Pins the measured 24-of-729 boundary.

        A naive filter that only drops `skill-` prefixed sources — the shape
        proposed in MemPalace PR #2053 — keeps 657 of these as user turns,
        a ~27x over-import of content the person never wrote.
        """
        events: list[dict[str, object]] = [session_start()]
        for index in range(611):
            events.append(
                event(
                    "user.message",
                    content=f"subagent task {index}",
                    parentAgentTaskId=f"task-{index}",
                )
            )
        for index in range(72):
            events.append(
                event("user.message", content="skill ctx", source=f"skill-{index}")
            )
        for index in range(16):
            events.append(
                event("user.message", content="agent ctx", source=f"agent-{index}")
            )
        for index in range(5):
            events.append(
                event("user.message", content="command ctx", source=f"command-{index}")
            )
        events.append(event("user.message", content="system ctx", source="system"))
        for index in range(24):
            events.append(event("user.message", content=f"human turn {index}"))

        result = self.extract(events)
        user_turns = [t for t in result["turns"] if t["role"] == "user"]

        self.assertEqual(729, 611 + 72 + 16 + 5 + 1 + 24)
        self.assertEqual(24, len(user_turns))
        self.assertEqual(611, result["dropped"]["user_subagent_prompt"])
        self.assertEqual(94, result["dropped"]["user_generated_context"])
        naive_kept = 729 - 72  # only `skill-` dropped
        self.assertEqual(657, naive_kept)
        self.assertGreater(naive_kept / len(user_turns), 25)


class SecretScanTests(unittest.TestCase):
    def test_detects_high_signal_credential_shapes(self) -> None:
        samples = {
            "aws-access-key-id": "AKIA" + "A" * 16,
            "github-token": "ghp_" + "b" * 36,
            "slack-token": "xoxb-" + "1" * 12,
            "private-key-block": "-----BEGIN RSA PRIVATE KEY-----",
            "json-web-token": "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT",
            "assigned-credential": 'api_key = "' + "c" * 20 + '"',
        }
        for name, text in samples.items():
            with self.subTest(pattern=name):
                findings = memory_provider._scan_secrets(text)
                self.assertIn(name, [f["pattern"] for f in findings])

    def test_ordinary_prose_is_not_flagged(self) -> None:
        self.assertEqual(
            [],
            memory_provider._scan_secrets(
                "We changed the retry policy because the gateway throttles bursts."
            ),
        )

    def test_redaction_masks_the_value(self) -> None:
        secret = "ghp_" + "d" * 36
        masked, count = memory_provider._redact_secrets(f"token is {secret} ok")
        self.assertEqual(1, count)
        self.assertNotIn(secret, masked)
        self.assertIn("[redacted:github-token]", masked)


class ProposeFromSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "memory"
        self.session = self.root / "session"
        self.session.mkdir()
        self.log = self.session / "events.jsonl"
        self.write_log(
            [
                session_start(),
                event("user.message", content="Why did the retry policy change?"),
                event("assistant.message", content="Because the gateway throttles."),
                event("user.message", content="subagent", parentAgentTaskId="t-1"),
            ]
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_log(self, events: list[dict[str, object]]) -> None:
        self.log.write_bytes(log_bytes(events))

    def invoke(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = memory_provider.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def base_args(self) -> list[str]:
        return [
            "--home",
            str(self.home),
            "--project",
            "mbeacom/context-kit",
            "--repo",
            str(REPO_ROOT),
        ]

    def candidates(self) -> list[Path]:
        root = self.home / "candidates"
        return sorted(root.rglob("*.md")) if root.exists() else []

    def test_dry_run_is_the_default_and_writes_nothing(self) -> None:
        result, stdout, stderr = self.invoke(
            ["propose-from-session", str(self.log), *self.base_args()]
        )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual("dry-run", payload["status"])
        self.assertEqual(1, len(payload["candidates"]))
        self.assertEqual([], payload["written"])
        self.assertEqual([], self.candidates())

    def test_write_emits_a_candidate_bound_to_the_source(self) -> None:
        result, stdout, stderr = self.invoke(
            ["propose-from-session", str(self.log), "--write", *self.base_args()]
        )
        self.assertEqual(0, result, stderr)
        payload = json.loads(stdout)
        self.assertEqual("extracted", payload["status"])
        written = self.candidates()
        self.assertEqual(1, len(written))
        document = written[0].read_text(encoding="utf-8")
        digest = hashlib.sha256(self.log.read_bytes()).hexdigest()
        self.assertIn(f"source_hash: {digest}", document)
        self.assertIn(f"schema: {memory_provider.CANDIDATE_SCHEMA}", document)
        # A candidate is explicitly not a memory record.
        self.assertNotIn("schema: context-kit/memory-v1", document)
        self.assertIn("review: candidate", document)
        self.assertIn("Why did the retry policy change?", document)
        self.assertNotIn("subagent", document.split("## Transcript")[1])

    def test_candidates_are_project_isolated(self) -> None:
        self.invoke(
            ["propose-from-session", str(self.log), "--write", *self.base_args()]
        )
        written = self.candidates()[0]
        slug = memory_provider.Config(
            provider="none",
            home=self.home,
            project="mbeacom/context-kit",
            auto_capture=False,
        ).project_slug
        self.assertEqual(slug, written.parent.name)

    def test_credentials_block_the_write_until_redaction_is_requested(self) -> None:
        self.write_log(
            [
                session_start(),
                event("user.message", content="the key is AKIA" + "Z" * 16),
            ]
        )
        _, stdout, _ = self.invoke(
            ["propose-from-session", str(self.log), "--write", *self.base_args()]
        )
        payload = json.loads(stdout)
        self.assertEqual([], payload["written"])
        self.assertEqual("possible-credentials", payload["blocked"][0]["reason"])
        self.assertEqual([], self.candidates())

        _, stdout, _ = self.invoke(
            [
                "propose-from-session",
                str(self.log),
                "--write",
                "--redact",
                *self.base_args(),
            ]
        )
        payload = json.loads(stdout)
        self.assertEqual(1, len(payload["written"]))
        document = self.candidates()[0].read_text(encoding="utf-8")
        self.assertNotIn("AKIA" + "Z" * 16, document)
        self.assertIn("[redacted:aws-access-key-id]", document)

    def test_sessions_without_conversation_are_skipped(self) -> None:
        self.write_log([session_start()])
        _, stdout, _ = self.invoke(
            ["propose-from-session", str(self.log), "--write", *self.base_args()]
        )
        payload = json.loads(stdout)
        self.assertEqual("no-conversational-turns", payload["skipped"][0]["reason"])
        self.assertEqual([], self.candidates())

    def test_non_copilot_logs_are_skipped_not_imported_raw(self) -> None:
        self.log.write_text('{"some":"other tool"}\n', encoding="utf-8")
        _, stdout, _ = self.invoke(
            ["propose-from-session", str(self.log), "--write", *self.base_args()]
        )
        payload = json.loads(stdout)
        self.assertEqual("not-a-copilot-session", payload["skipped"][0]["reason"])

    def test_a_missing_path_is_refused(self) -> None:
        result, _, stderr = self.invoke(
            ["propose-from-session", str(self.root / "absent"), *self.base_args()]
        )
        self.assertEqual(2, result)
        self.assertIn("does not exist", stderr)

    def test_project_mismatch_is_refused(self) -> None:
        result, _, stderr = self.invoke(
            [
                "propose-from-session",
                str(self.log),
                "--home",
                str(self.home),
                "--project",
                "someone/else",
                "--repo",
                str(REPO_ROOT),
            ]
        )
        self.assertEqual(2, result)
        self.assertEqual([], self.candidates())
        self.assertTrue(stderr.strip())


if __name__ == "__main__":
    unittest.main()
