from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "plugins/plugin-forge/scripts"

# agent_frontmatter imports command_frontmatter as a sibling module, so the
# scripts dir must be importable before it is loaded.
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "agent_frontmatter", SCRIPTS / "agent_frontmatter.py"
)
assert SPEC and SPEC.loader
agent_frontmatter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agent_frontmatter
SPEC.loader.exec_module(agent_frontmatter)

HEADER = """\
---
name: a1
description: "Use when exercising the agent frontmatter gate in tests."
tools: Read, Grep, Glob
"""


def agent(skills_block: str | None) -> str:
    body = HEADER
    if skills_block is not None:
        body += skills_block.rstrip("\n") + "\n"
    return body + "---\n\nAgent body.\n"


class Harness(unittest.TestCase):
    """Builds a throwaway plugins/ tree so the gate runs end to end."""

    def run_gate(self, skills_block: str | None, skills: tuple[str, ...] = ("s1",)):
        with tempfile.TemporaryDirectory() as tmp:
            plugins = Path(tmp) / "plugins"
            (plugins / "p/agents").mkdir(parents=True)
            for name in skills:
                skill_dir = plugins / "p/skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: "
                    f'"Use when exercising the gate."\n---\n\nBody.\n',
                    encoding="utf-8",
                )
            (plugins / "p/agents/a1.md").write_text(
                agent(skills_block), encoding="utf-8"
            )
            return agent_frontmatter.validate_plugins(plugins)

    def assertAccepted(self, block: str | None, **kwargs) -> None:
        result = self.run_gate(block, **kwargs)
        self.assertEqual(result.errors, [], f"expected accepted:\n{block}")

    def assertRejected(self, block: str | None, needle: str = "", **kwargs) -> None:
        result = self.run_gate(block, **kwargs)
        self.assertTrue(result.errors, f"expected rejected:\n{block}")
        if needle:
            joined = "\n".join(result.errors)
            self.assertIn(needle, joined)


class AcceptedShapes(Harness):
    def test_block_sequence(self) -> None:
        self.assertAccepted("skills:\n  - s1")

    def test_block_sequence_multiple(self) -> None:
        self.assertAccepted("skills:\n  - s1\n  - s2", skills=("s1", "s2"))

    def test_flow_sequence(self) -> None:
        self.assertAccepted("skills: [s1]")

    def test_flow_sequence_multiple(self) -> None:
        self.assertAccepted("skills: [s1, s2]", skills=("s1", "s2"))

    def test_quoted_items(self) -> None:
        self.assertAccepted('skills:\n  - "s1"')

    def test_quoted_flow_items(self) -> None:
        self.assertAccepted("skills: ['s1', \"s2\"]", skills=("s1", "s2"))

    def test_absent_skills_key_is_fine(self) -> None:
        self.assertAccepted(None)

    def test_inline_comment_then_block_sequence(self) -> None:
        """Regression: a comment-only inline value must defer to the body.

        The first implementation read any non-empty text after `skills:` as a
        scalar and rejected this, blocking legal YAML in pre-commit.
        """
        self.assertAccepted("skills: # preloaded\n  - s1")

    def test_anchor_then_block_sequence(self) -> None:
        """Regression: `skills: &ref` + a list is an anchored sequence."""
        self.assertAccepted("skills: &ref\n  - s1")

    def test_comment_line_between_items(self) -> None:
        self.assertAccepted("skills:\n  # a note\n  - s1")

    def test_trailing_comment_on_flow(self) -> None:
        self.assertAccepted("skills: [s1] # preloaded")

    def test_trailing_comment_on_block_item(self) -> None:
        """Review regression: `- s1 # note` is the skill `s1`, not `s1 # note`.

        Comparing the raw item text rejected valid YAML with a nonsense message
        naming a skill nobody wrote.
        """
        self.assertAccepted("skills:\n  - s1 # note")

    def test_trailing_comment_on_quoted_item(self) -> None:
        self.assertAccepted('skills:\n  - "s1" # note')


class RejectedShapes(Harness):
    def test_bare_scalar(self) -> None:
        self.assertRejected("skills: s1", "must be a YAML list")

    def test_comma_separated_string(self) -> None:
        """The exact bug this gate exists to prevent."""
        self.assertRejected("skills: s1, s2", "must be a YAML list")

    def test_scalar_suggestion_lists_each_skill(self) -> None:
        result = self.run_gate("skills: s1, s2")
        joined = "\n".join(result.errors)
        self.assertIn("  - s1", joined)
        self.assertIn("  - s2", joined)

    def test_quoted_scalar(self) -> None:
        self.assertRejected('skills: "s1"', "must be a YAML list")

    def test_empty_skills_key(self) -> None:
        self.assertRejected("skills:", "lists no skills")

    def test_comment_only_with_no_body(self) -> None:
        self.assertRejected("skills: # nothing follows", "lists no skills")

    def test_empty_flow_sequence(self) -> None:
        self.assertRejected("skills: []", "lists no skills")

    def test_unknown_skill(self) -> None:
        self.assertRejected("skills:\n  - nope", "unknown skill")

    def test_unknown_skill_in_flow(self) -> None:
        self.assertRejected("skills: [nope]", "unknown skill")

    def test_nested_flow_sequence(self) -> None:
        """Regression: the first implementation PASSED this.

        `strip("[]")` removed both bracket pairs, so `[[s1]]` looked like the
        valid `[s1]`. Copilot validates array-of-strings and would reject it,
        which is the false negative this gate must never produce.
        """
        self.assertRejected("skills: [[s1]]", "not a string")

    def test_mapping_item_in_flow(self) -> None:
        self.assertRejected("skills: [{a: b}]", "not a string")

    def test_stray_line_in_block_sequence(self) -> None:
        """Review regression: this was ACCEPTED.

        A non-item line makes the block invalid YAML, so the host rejects the
        whole frontmatter — but the gate skipped the line and passed on the
        valid item beside it, recreating the registration failure it exists to
        prevent.
        """
        self.assertRejected("skills:\n  - s1\n  unexpected", "non-item line")

    def test_bool_item_is_not_a_string(self) -> None:
        self.assertRejected("skills:\n  - true", "resolves to a YAML bool")

    def test_int_item_is_not_a_string(self) -> None:
        self.assertRejected("skills:\n  - 123", "resolves to a YAML int")

    def test_null_item_is_not_a_string(self) -> None:
        self.assertRejected("skills:\n  - ~", "resolves to a YAML null")

    def test_item_without_space_after_dash_is_a_scalar(self) -> None:
        """`  -s1` is the plain scalar `-s1`, so the whole value is a string."""
        self.assertRejected("skills:\n  -s1", "must be a YAML list")

    def test_later_item_without_space_after_dash(self) -> None:
        self.assertRejected("skills:\n  - s1\n  -s2", "space after the dash")

    def test_unterminated_flow_sequence(self) -> None:
        self.assertRejected("skills: [s1", "unterminated")

    def test_mapping_value(self) -> None:
        self.assertRejected("skills:\n  a: b", "must be a YAML list")

    def test_valueless_list_item(self) -> None:
        self.assertRejected("skills:\n  -\n  - s1", "no value")


class ScalarTextTests(unittest.TestCase):
    def test_drops_trailing_comment(self) -> None:
        self.assertEqual(agent_frontmatter.scalar_text("s1 # note"), "s1")

    def test_unquotes(self) -> None:
        self.assertEqual(agent_frontmatter.scalar_text('"s1"'), "s1")
        self.assertEqual(agent_frontmatter.scalar_text("'s1'"), "s1")

    def test_unquotes_then_drops_comment(self) -> None:
        self.assertEqual(agent_frontmatter.scalar_text('"s1" # note'), "s1")

    def test_preserves_hash_inside_quotes(self) -> None:
        self.assertEqual(agent_frontmatter.scalar_text('"s#1"'), "s#1")


class SplitFlowTests(unittest.TestCase):
    def test_respects_nesting(self) -> None:
        self.assertEqual(agent_frontmatter._split_flow("[a, [b, c]]"), ["a", "[b, c]"])

    def test_respects_quotes(self) -> None:
        self.assertEqual(agent_frontmatter._split_flow('["a, b", c]'), ['"a, b"', "c"])

    def test_unterminated_returns_none(self) -> None:
        self.assertIsNone(agent_frontmatter._split_flow("[a, b"))

    def test_trailing_junk_returns_none(self) -> None:
        self.assertIsNone(agent_frontmatter._split_flow("[a] junk"))

    def test_trailing_comment_is_allowed(self) -> None:
        self.assertEqual(agent_frontmatter._split_flow("[a] # note"), ["a"])


class RepoTests(unittest.TestCase):
    def test_repo_agents_pass(self) -> None:
        result = agent_frontmatter.validate_plugins(REPO_ROOT / "plugins")
        self.assertEqual(result.errors, [])
        self.assertGreater(result.skills_checked, 0)

    def test_every_repo_agent_with_skills_uses_a_sequence(self) -> None:
        """Belt and braces: assert the shipped state directly, not just the gate."""
        for path in agent_frontmatter.discover_agents(REPO_ROOT / "plugins"):
            parsed = agent_frontmatter.parse_frontmatter(
                path.read_text(encoding="utf-8")
            )
            assert parsed is not None, path
            entry = parsed.entries.get("skills")
            if entry is None:
                continue
            self.assertEqual(
                agent_frontmatter.resolve_entry_type(entry),
                "seq",
                f"{path} must declare `skills` as a YAML sequence",
            )


if __name__ == "__main__":
    unittest.main()
