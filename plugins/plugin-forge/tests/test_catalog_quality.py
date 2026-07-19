from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "plugins/plugin-forge/scripts/catalog_quality.py"
SPEC = importlib.util.spec_from_file_location("catalog_quality", MODULE_PATH)
assert SPEC and SPEC.loader
catalog_quality = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = catalog_quality
SPEC.loader.exec_module(catalog_quality)


class CatalogQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.policy_path = self.repo / "policy.json"
        self.fixtures_path = self.repo / "fixtures.json"
        self.skill_path = "plugins/alpha/skills/alpha/SKILL.md"
        self.agent_path = "plugins/beta/agents/beta.md"
        self._write_component(
            self.skill_path,
            "alpha",
            "Use when searching source code for exact symbol definitions and callers.",
            "# Alpha\n",
        )
        self._write_component(
            self.agent_path,
            "beta",
            "Use to verify documented behavior against primary repository evidence.",
            "You verify claims without editing files.\n",
        )
        self.policy = {
            "aggregate_description_max_chars": 300,
            "similarity_threshold": 0.72,
            "minimum_positive_fixtures": 2,
            "minimum_negative_fixtures": 2,
            "similarity_allowlist": [],
            "agent_output_contracts": {},
        }
        self.fixtures = {
            "schema_version": 1,
            "components": {
                self.skill_path: {
                    "positive": [
                        "Search source code for the exact symbol definition.",
                        "Find every caller of this source function.",
                    ],
                    "negative": [
                        "Search a PDF for exact invoice totals.",
                        "Verify a release claim against repository evidence.",
                    ],
                },
                self.agent_path: {
                    "positive": [
                        "Verify this documented behavior using repository evidence.",
                        "Check each claim against primary source files.",
                    ],
                    "negative": [
                        "Edit the repository to implement the requested behavior.",
                        "Search repository history for why this line changed.",
                    ],
                },
            },
        }
        self._write_json()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_component(
        self, relative_path: str, name: str, description: str, body: str
    ) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'---\nname: {name}\ndescription: "{description}"\n---\n\n{body}',
            encoding="utf-8",
        )

    def _write_json(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.fixtures_path.write_text(json.dumps(self.fixtures), encoding="utf-8")

    def _validate(self):
        self._write_json()
        return catalog_quality.validate_repository(
            self.repo,
            policy_path=self.policy_path,
            fixtures_path=self.fixtures_path,
        )

    def test_valid_catalog_passes(self) -> None:
        result = self._validate()
        self.assertEqual([], result.errors)
        self.assertEqual(2, result.component_count)
        self.assertEqual(8, result.fixture_example_count)

    def test_aggregate_budget_failure_is_reported(self) -> None:
        self.policy["aggregate_description_max_chars"] = 20
        result = self._validate()
        self.assertTrue(
            any("exceeding budget 20" in error for error in result.errors),
            result.errors,
        )

    def test_similar_descriptions_fail_unless_pair_is_allowlisted(self) -> None:
        description = (
            "Use when searching source code for exact symbol definitions and callers."
        )
        self._write_component(
            self.agent_path,
            "beta",
            description,
            "You search without editing files.\n",
        )
        self.fixtures["components"][self.agent_path] = {
            "positive": [
                "Search source code for an exact symbol definition.",
                "Find source callers of this specific symbol.",
            ],
            "negative": [
                "Search a PDF for an exact invoice definition.",
                "Edit source code after locating the symbol.",
            ],
        }
        result = self._validate()
        self.assertTrue(
            any("descriptions too similar" in error for error in result.errors),
            result.errors,
        )

        self.policy["similarity_allowlist"] = [
            {
                "components": [self.skill_path, self.agent_path],
                "reason": "Test-only intentional overlap between paired components.",
            }
        ]
        result = self._validate()
        self.assertFalse(
            any("descriptions too similar" in error for error in result.errors),
            result.errors,
        )

    def test_identical_single_content_token_descriptions_score_one(self) -> None:
        score = catalog_quality.description_similarity(
            "Use when auditing.",
            "Use when auditing.",
        )
        self.assertEqual(1.0, score)

    def test_fixture_coverage_and_quality_failures_are_reported(self) -> None:
        del self.fixtures["components"][self.agent_path]
        self.fixtures["components"][self.skill_path]["positive"][0] = "Too short"
        result = self._validate()
        self.assertTrue(
            any("missing component" in error for error in result.errors),
            result.errors,
        )
        self.assertTrue(
            any("too weak" in error for error in result.errors),
            result.errors,
        )

    def test_declared_output_contract_terms_are_enforced(self) -> None:
        self._write_component(
            self.agent_path,
            "beta",
            "Use to verify documented behavior against primary repository evidence.",
            "## Output contract\n\nReturn RESULT with a source pointer.\n",
        )
        self.policy["agent_output_contracts"] = {
            self.agent_path: {
                "marker": "## Output contract",
                "required_terms": ["RESULT", "EVIDENCE"],
            }
        }
        result = self._validate()
        self.assertTrue(
            any("missing required term `EVIDENCE`" in error for error in result.errors),
            result.errors,
        )

    def test_fractional_fixture_minimum_is_rejected(self) -> None:
        self.policy["minimum_positive_fixtures"] = 2.9
        result = self._validate()
        self.assertTrue(
            any(
                "`minimum_positive_fixtures` must be an integer" in error
                for error in result.errors
            ),
            result.errors,
        )


if __name__ == "__main__":
    unittest.main()
