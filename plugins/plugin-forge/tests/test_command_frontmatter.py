from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "plugins/plugin-forge/scripts/command_frontmatter.py"
SPEC = importlib.util.spec_from_file_location("command_frontmatter", MODULE_PATH)
assert SPEC and SPEC.loader
command_frontmatter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = command_frontmatter
SPEC.loader.exec_module(command_frontmatter)

VALID = """\
---
description: Do a bounded, useful thing for the active repository task.
argument-hint: "[artifact-path]"
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*)
---

Body text.
"""


class ResolveTypeTests(unittest.TestCase):
    def test_plain_and_quoted_scalars_are_strings(self) -> None:
        for raw in (
            '"[artifact-path]"',
            "'[corpus-root]'",
            "<task to decompose and execute>",
            "<proposed change, diff, commit, PR, or design decision>",
            "Read, Grep, Glob, Bash(git:*)",
            "'<new-plugin-name> [\"short description\"]'",
            "|",
            ">",
            "0.1.0.4",
            "1.2.3",
            "v1",
            # YAML 1.1 needs a mantissa dot and an explicit exponent sign, so
            # this is a string, not a float. Confirmed against PyYAML.
            "1e3",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), "str")

    def test_bracketed_value_resolves_to_a_sequence(self) -> None:
        # The exact regression: `argument-hint: [artifact-path]`.
        self.assertEqual(command_frontmatter.resolve_type("[artifact-path]"), "seq")
        self.assertEqual(command_frontmatter.resolve_type("[corpus-root]"), "seq")

    def test_other_non_string_yaml_types(self) -> None:
        cases = {
            "{a: b}": "map",
            "true": "bool",
            "False": "bool",
            "yes": "bool",
            "off": "bool",
            "null": "null",
            "~": "null",
            "": "null",
            "42": "int",
            "-7": "int",
            "0x1f": "int",
            "017": "int",
            "3.14": "float",
            ".inf": "float",
            ".nan": "float",
            "2026-01-01": "timestamp",
            "*x": "malformed",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), expected)

    def test_pyyaml_parity_for_near_miss_scalars(self) -> None:
        """Values that *look* typed but that PyYAML resolves as strings.

        Each expectation was checked against PyYAML's implicit resolvers; the
        gate ports those regexes so it never fails a command YAML accepts.
        """
        for raw in (
            "1e3",  # YAML 1.1 needs an explicit exponent sign
            "1.0e3",
            "0o17",  # YAML 1.1 octal is `017`
            "y",  # PyYAML omits the single-letter booleans
            "n",
            "-.5",  # a signed float needs digits before the dot
            "09",  # not octal, not decimal
            "2026-1-1",  # the date-only form needs two-digit month and day
            "&x v",  # an anchor resolves to the value it decorates
            "!!str 5",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), "str")

    def test_trailing_comment_does_not_change_the_type(self) -> None:
        self.assertEqual(command_frontmatter.resolve_type("[a] # note"), "seq")
        self.assertEqual(command_frontmatter.resolve_type('"[a]" # note'), "str")

    def test_comment_only_value_is_null(self) -> None:
        # `description: # TODO` is null in YAML, not the text "# TODO".
        for raw in ("# TODO", "#", "  # trailing thought  "):
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), "null")

    def test_malformed_quoted_scalars(self) -> None:
        for raw in (
            '"unterminated',
            "'unterminated",
            '"closed" then junk',
            "'closed' then junk",
            '"escaped \\" but never closed',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), "malformed")

    def test_well_formed_quoted_scalars_with_escapes(self) -> None:
        for raw in (
            '"has \\"inner\\" quotes"',
            "'it''s fine'",
            '"trailing" # comment',
            "'<new-plugin-name> [\"short description\"]'",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(command_frontmatter.resolve_type(raw), "str")


class ValidateCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.plugins = self.repo / "plugins"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write(
        self, text: str, *, plugin: str = "demo", name: str = "do-thing"
    ) -> None:
        path = self.plugins / plugin / "commands" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _errors(self) -> list[str]:
        return command_frontmatter.validate_plugins(self.plugins).errors

    def test_valid_command_passes(self) -> None:
        self._write(VALID)
        result = command_frontmatter.validate_plugins(self.plugins)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.command_count, 1)

    def test_unquoted_bracket_hint_is_rejected(self) -> None:
        self._write(VALID.replace('"[artifact-path]"', "[artifact-path]"))
        errors = self._errors()
        self.assertTrue(
            any("`argument-hint` must be a string" in e and "seq" in e for e in errors),
            errors,
        )

    def test_boolean_field_must_be_boolean(self) -> None:
        self._write(
            VALID.replace(
                "---\n\nBody", 'disable-model-invocation: "true"\n---\n\nBody'
            )
        )
        errors = self._errors()
        self.assertTrue(
            any("`disable-model-invocation` must be a boolean" in e for e in errors),
            errors,
        )

    def test_boolean_field_accepts_a_real_boolean(self) -> None:
        self._write(
            VALID.replace("---\n\nBody", "disable-model-invocation: true\n---\n\nBody")
        )
        self.assertEqual(self._errors(), [])

    def test_missing_frontmatter_is_rejected(self) -> None:
        self._write("Just a body with no frontmatter.\n")
        self.assertTrue(any("missing YAML frontmatter" in e for e in self._errors()))

    def test_unterminated_frontmatter_is_rejected(self) -> None:
        self._write("---\ndescription: Something reasonable and long enough here.\n")
        self.assertTrue(any("never closed" in e for e in self._errors()))

    def test_missing_description_is_rejected(self) -> None:
        self._write('---\nargument-hint: "[path]"\n---\n\nBody.\n')
        self.assertTrue(any("missing `description`" in e for e in self._errors()))

    def test_empty_string_field_is_rejected(self) -> None:
        self._write(VALID.replace('argument-hint: "[artifact-path]"', "argument-hint:"))
        self.assertTrue(
            any("`argument-hint` is empty" in e for e in self._errors()),
            self._errors(),
        )

    def test_unknown_key_is_rejected(self) -> None:
        self._write(VALID.replace("argument-hint:", "argument_hint:"))
        self.assertTrue(
            any("unknown frontmatter key `argument_hint`" in e for e in self._errors()),
            self._errors(),
        )

    def test_duplicate_key_is_rejected(self) -> None:
        self._write(
            VALID.replace("---\n\nBody", 'argument-hint: "[other]"\n---\n\nBody')
        )
        self.assertTrue(any("duplicate key" in e for e in self._errors()))

    def test_unquoted_colon_in_plain_scalar_is_rejected(self) -> None:
        self._write(VALID.replace("description: Do a", "description: Warning: do a"))
        self.assertTrue(
            any("unquoted `:`" in e for e in self._errors()), self._errors()
        )

    def test_colon_without_space_is_rejected(self) -> None:
        self._write(VALID.replace("argument-hint: ", "argument-hint:"))
        self.assertTrue(
            any("needs a space after the colon" in e for e in self._errors()),
            self._errors(),
        )

    def test_tool_pattern_colon_is_not_flagged(self) -> None:
        # `Bash(git:*)` has no space after the colon, so it stays a plain scalar.
        self._write(VALID)
        self.assertEqual(self._errors(), [])

    def test_missing_plugins_dir_is_reported(self) -> None:
        result = command_frontmatter.validate_plugins(self.repo / "nope")
        self.assertTrue(any("plugins dir not found" in e for e in result.errors))

    def test_comment_only_value_is_rejected(self) -> None:
        self._write(
            VALID.replace('argument-hint: "[artifact-path]"', "argument-hint: # TODO")
        )
        self.assertTrue(
            any("`argument-hint` is empty" in e for e in self._errors()),
            self._errors(),
        )

    def test_comment_only_description_is_rejected(self) -> None:
        self._write("---\ndescription: # TODO\n---\n\nBody.\n")
        self.assertTrue(
            any("`description` is empty" in e for e in self._errors()),
            self._errors(),
        )

    def test_unterminated_quote_is_rejected(self) -> None:
        self._write(VALID.replace('"[artifact-path]"', '"[artifact-path]'))
        self.assertTrue(
            any("`argument-hint` is not valid YAML" in e for e in self._errors()),
            self._errors(),
        )

    def test_quoted_value_with_trailing_junk_is_rejected(self) -> None:
        self._write(VALID.replace('"[artifact-path]"', '"[artifact-path]" oops'))
        self.assertTrue(
            any("`argument-hint` is not valid YAML" in e for e in self._errors()),
            self._errors(),
        )

    def test_nested_mapping_is_rejected(self) -> None:
        self._write("---\ndescription:\n  text: value\n---\n\nBody.\n")
        errors = self._errors()
        self.assertTrue(
            any("`description` must be a string" in e and "map" in e for e in errors),
            errors,
        )

    def test_nested_sequence_is_rejected(self) -> None:
        self._write(
            VALID.replace(
                "allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*)",
                "allowed-tools:\n  - Read\n  - Grep",
            )
        )
        errors = self._errors()
        self.assertTrue(
            any("`allowed-tools` must be a string" in e and "seq" in e for e in errors),
            errors,
        )

    def test_mapping_under_a_plain_scalar_is_rejected(self) -> None:
        self._write("---\ndescription: Some text\n  other: value\n---\n\nBody.\n")
        self.assertTrue(
            any("`description` is not valid YAML" in e for e in self._errors()),
            self._errors(),
        )

    def test_indented_plain_scalar_is_accepted(self) -> None:
        self._write(
            "---\ndescription:\n  A description that lives on the next line.\n---\n\nB.\n"
        )
        self.assertEqual(self._errors(), [])

    def test_block_scalar_is_accepted(self) -> None:
        self._write(
            "---\ndescription: >-\n  A folded description spanning\n"
            "  two source lines.\n---\n\nBody.\n"
        )
        self.assertEqual(self._errors(), [])

    def test_wrapped_plain_scalar_is_accepted(self) -> None:
        self._write(
            "---\ndescription: A description that wraps\n  onto a second line.\n"
            "---\n\nBody.\n"
        )
        self.assertEqual(self._errors(), [])

    def test_no_commands_is_not_an_error(self) -> None:
        self.plugins.mkdir(parents=True, exist_ok=True)
        result = command_frontmatter.validate_plugins(self.plugins)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.command_count, 0)


class RepositoryTests(unittest.TestCase):
    def test_shipped_commands_are_valid(self) -> None:
        result = command_frontmatter.validate_plugins(REPO_ROOT / "plugins")
        self.assertEqual(result.errors, [])
        self.assertGreater(result.command_count, 0)


class MainTests(unittest.TestCase):
    def test_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            plugins = Path(name) / "plugins"
            path = plugins / "demo/commands/do-thing.md"
            path.parent.mkdir(parents=True, exist_ok=True)

            path.write_text(VALID, encoding="utf-8")
            self.assertEqual(command_frontmatter.main([str(plugins)]), 0)

            path.write_text(
                VALID.replace('"[artifact-path]"', "[artifact-path]"), encoding="utf-8"
            )
            self.assertEqual(command_frontmatter.main([str(plugins)]), 1)


if __name__ == "__main__":
    unittest.main()
