from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SERVER = PLUGIN_ROOT / "src" / "memorykit" / "mcp.py"
SPEC = importlib.util.spec_from_file_location("memory_mcp_server", SERVER)
assert SPEC is not None and SPEC.loader is not None
server = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)


class McpUnitTests(unittest.TestCase):
    def test_protocol_negotiation_echoes_a_supported_version(self) -> None:
        for version in server.SUPPORTED_PROTOCOLS:
            self.assertEqual(version, server._negotiate(version))

    def test_unknown_protocol_falls_back_to_the_newest_supported(self) -> None:
        self.assertEqual(server.SUPPORTED_PROTOCOLS[0], server._negotiate("1999-01-01"))
        self.assertEqual(server.SUPPORTED_PROTOCOLS[0], server._negotiate(None))

    def test_frontmatter_reader_stops_at_the_closing_fence(self) -> None:
        document = "---\nreview: proposed\n---\n\nreview: accepted\n"
        self.assertEqual("proposed", server._frontmatter_value(document, "review"))

    def test_frontmatter_reader_rejects_a_document_without_frontmatter(self) -> None:
        self.assertIsNone(server._frontmatter_value("no frontmatter here", "review"))

    def test_the_exposed_surface_stays_minimal_and_non_destructive(self) -> None:
        names = {tool["name"] for tool in server.TOOLS}
        self.assertEqual({"memory_recall", "memory_capture", "memory_review"}, names)
        # Every connected tool costs schema tokens each turn, and destructive
        # or reconciling operations stay explicit CLI work.
        for forbidden in ("sync", "delete", "remove", "record_state", "promote"):
            self.assertFalse(
                any(forbidden in name for name in names),
                f"{forbidden!r} must not be exposed over MCP",
            )

    def test_every_tool_declares_a_closed_input_schema(self) -> None:
        for tool in server.TOOLS:
            with self.subTest(tool=tool["name"]):
                schema = tool["inputSchema"]
                self.assertEqual("object", schema["type"])
                self.assertFalse(schema["additionalProperties"])
                self.assertTrue(tool["description"].strip())


class McpProtocolTests(unittest.TestCase):
    """Drives the server over real stdio, the way a host would."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "memory"
        self.source = self.root / "source.txt"
        self.source.write_text("verified source\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def converse(
        self,
        messages: list[dict[str, object]],
        *,
        project: str | None = "mbeacom/context-kit",
    ) -> list[dict[str, object]]:
        env = dict(os.environ)
        env["CONTEXT_KIT_MEMORY_HOME"] = str(self.home)
        if project is None:
            env.pop("CONTEXT_KIT_MEMORY_PROJECT", None)
        else:
            env["CONTEXT_KIT_MEMORY_PROJECT"] = project
        payload = "\n".join(json.dumps(message) for message in messages) + "\n"
        result = subprocess.run(
            [sys.executable, str(SERVER)],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=180,
            env=env,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())
        return [
            json.loads(line)
            for line in result.stdout.decode().splitlines()
            if line.strip()
        ]

    def record(self, record_id: str, review: str) -> str:
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        return "\n".join(
            [
                "---",
                "schema: context-kit/memory-v1",
                f"id: {record_id}",
                "type: decision",
                "scope: project",
                "repository: mbeacom/context-kit",
                "branch: main",
                "head: 1234567",
                "observed_at: 2026-01-01T00:00:00Z",
                "captured_at: 2026-01-01T00:00:00Z",
                "freshness: current",
                f"review: {review}",
                f"source: {self.source}",
                f"source_hash: {digest}",
                "---",
                "",
                "## Primary Memory",
                "",
                "Retries are capped at five attempts because the gateway throttles.",
                "",
                "## Cue Anchors",
                "",
                "- retry policy",
                "",
                "## Evidence",
                "",
                f"- `{self.source}:1` — the captured source.",
                "",
                "## Supersedes",
                "",
                "- None.",
                "",
                "## Review Notes",
                "",
                "- Captured through the MCP contract tests.",
                "",
            ]
        )

    @staticmethod
    def call(
        request_id: int, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }

    @staticmethod
    def text(response: dict[str, object]) -> str:
        return response["result"]["content"][0]["text"]  # type: ignore[index]

    def test_initialize_handshake(self) -> None:
        responses = self.converse(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        # The notification must not produce a response.
        self.assertEqual(2, len(responses))
        initialized = responses[0]["result"]
        self.assertEqual("2025-03-26", initialized["protocolVersion"])
        self.assertEqual("context-kit-memory", initialized["serverInfo"]["name"])
        self.assertIn("tools", initialized["capabilities"])
        listed = [tool["name"] for tool in responses[1]["result"]["tools"]]
        self.assertEqual(["memory_recall", "memory_capture", "memory_review"], listed)

    def test_malformed_input_does_not_end_the_session(self) -> None:
        responses = self.converse([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
        self.assertEqual({}, responses[0]["result"])

        env = dict(os.environ, CONTEXT_KIT_MEMORY_HOME=str(self.home))
        result = subprocess.run(
            [sys.executable, str(SERVER)],
            input=b'not json\n{"jsonrpc":"1.0","id":9}\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n',
            capture_output=True,
            check=False,
            timeout=60,
            env=env,
        )
        lines = [json.loads(line) for line in result.stdout.decode().splitlines()]
        self.assertEqual(server.PARSE_ERROR, lines[0]["error"]["code"])
        self.assertEqual(server.INVALID_REQUEST, lines[1]["error"]["code"])
        # The loop survived both and still answered the valid frame.
        self.assertEqual({}, lines[2]["result"])

    def test_unknown_method_and_tool_are_reported_distinctly(self) -> None:
        responses = self.converse(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "does/not/exist"},
                self.call(2, "memory_delete", {}),
            ]
        )
        self.assertEqual(server.METHOD_NOT_FOUND, responses[0]["error"]["code"])
        self.assertEqual(server.INVALID_PARAMS, responses[1]["error"]["code"])

    def test_capture_persists_a_proposed_record(self) -> None:
        responses = self.converse(
            [
                self.call(
                    1, "memory_capture", {"record": self.record("retry", "proposed")}
                )
            ]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"], self.text(responses[0]))
        payload = json.loads(self.text(responses[0]))
        self.assertEqual("created", payload["status"])

    def test_capture_refuses_to_activate_memory(self) -> None:
        # `capture` derives initial state from frontmatter, so without this
        # guard the MCP surface could accept its own proposals.
        for review in ("accepted", "rejected"):
            with self.subTest(review=review):
                responses = self.converse(
                    [
                        self.call(
                            1,
                            "memory_capture",
                            {"record": self.record("retry", review)},
                        )
                    ]
                )
                self.assertTrue(responses[0]["result"]["isError"])
                self.assertIn("can only propose", self.text(responses[0]))

    def test_a_captured_proposal_is_inert_in_recall(self) -> None:
        responses = self.converse(
            [
                self.call(
                    1, "memory_capture", {"record": self.record("retry", "proposed")}
                ),
                self.call(2, "memory_recall", {"query": "retry policy gateway"}),
            ]
        )
        recall = json.loads(self.text(responses[1]))
        self.assertEqual([], recall["records"])
        self.assertEqual(
            [("retry", "proposed")],
            [(r["id"], r["review"]) for r in recall["inactive_records"]],
        )

    def test_capture_rejects_a_document_without_frontmatter(self) -> None:
        responses = self.converse(
            [self.call(1, "memory_capture", {"record": "just some prose"})]
        )
        self.assertTrue(responses[0]["result"]["isError"])
        self.assertIn("frontmatter", self.text(responses[0]))

    def test_capture_enforces_the_contract_via_the_provider(self) -> None:
        # A fabricated source_hash must fail validation, not be trusted.
        forged = self.record("retry", "proposed").replace(
            hashlib.sha256(self.source.read_bytes()).hexdigest(), "0" * 64
        )
        responses = self.converse([self.call(1, "memory_capture", {"record": forged})])
        self.assertTrue(responses[0]["result"]["isError"])

    def test_recall_validates_its_arguments(self) -> None:
        responses = self.converse(
            [
                self.call(1, "memory_recall", {"query": ""}),
                self.call(2, "memory_recall", {"query": "x", "results": 999}),
                self.call(3, "memory_recall", {"query": "x", "results": "eight"}),
            ]
        )
        for response in responses:
            self.assertTrue(response["result"]["isError"])

    def test_review_is_read_only_and_takes_no_arguments(self) -> None:
        responses = self.converse(
            [
                self.call(
                    1, "memory_capture", {"record": self.record("retry", "proposed")}
                ),
                self.call(2, "memory_review", {}),
                self.call(3, "memory_review", {"unexpected": True}),
            ]
        )
        payload = json.loads(self.text(responses[1]))
        self.assertEqual(["retry"], [r["id"] for r in payload["records"]])
        self.assertTrue(responses[2]["result"]["isError"])

    def test_capture_refuses_a_source_that_does_not_exist(self) -> None:
        # validate_memory verifies source_hash only when the source exists, so
        # without this gate any 64-character hash would be accepted alongside
        # a fabricated path and the advertised provenance check would be a lie.
        absent = self.root / "never-written.txt"
        forged = self.record("retry", "proposed").replace(
            f"source: {self.source}", f"source: {absent}"
        )
        responses = self.converse([self.call(1, "memory_capture", {"record": forged})])
        self.assertTrue(responses[0]["result"]["isError"])
        self.assertIn("does not exist", self.text(responses[0]))

    def test_capture_refuses_a_record_without_a_source(self) -> None:
        stripped = "\n".join(
            line
            for line in self.record("retry", "proposed").splitlines()
            if not line.startswith("source: ")
        )
        responses = self.converse(
            [self.call(1, "memory_capture", {"record": stripped})]
        )
        self.assertTrue(responses[0]["result"]["isError"])
        self.assertIn("`source`", self.text(responses[0]))

    def test_the_claude_userconfig_project_fallback_is_honored(self) -> None:
        # A Claude install configured through the plugin's `project` option
        # sets only CLAUDE_PLUGIN_OPTION_PROJECT; checking just the portable
        # name would make every tool refuse on an otherwise valid setup.
        env = dict(os.environ)
        env["CONTEXT_KIT_MEMORY_HOME"] = str(self.home)
        env.pop("CONTEXT_KIT_MEMORY_PROJECT", None)
        env["CLAUDE_PLUGIN_OPTION_PROJECT"] = "mbeacom/context-kit"
        payload = json.dumps(self.call(1, "memory_review", {})) + "\n"
        result = subprocess.run(
            [sys.executable, str(SERVER)],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=120,
            env=env,
        )
        response = json.loads(result.stdout.decode().splitlines()[0])
        self.assertFalse(
            response["result"]["isError"], response["result"]["content"][0]["text"]
        )

    def test_an_unset_project_refuses_rather_than_using_a_global_store(self) -> None:
        responses = self.converse(
            [self.call(1, "memory_recall", {"query": "anything"})], project=None
        )
        self.assertTrue(responses[0]["result"]["isError"])
        self.assertIn("CONTEXT_KIT_MEMORY_PROJECT", self.text(responses[0]))

    def test_projects_are_isolated_from_one_another(self) -> None:
        self.converse(
            [
                self.call(
                    1, "memory_capture", {"record": self.record("retry", "proposed")}
                )
            ]
        )
        other = self.converse(
            [self.call(1, "memory_review", {})], project="someone/else"
        )
        payload = json.loads(self.text(other[0]))
        self.assertEqual([], payload["records"])


if __name__ == "__main__":
    unittest.main()
