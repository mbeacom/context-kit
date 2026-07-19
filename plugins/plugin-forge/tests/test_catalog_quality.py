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
        self.retrieval_path = self.repo / "retrieval-scenarios.json"
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
        self.marketplace = {
            "name": "test-marketplace",
            "plugins": [
                {"name": "alpha", "source": "./plugins/alpha"},
                {"name": "beta", "source": "./plugins/beta"},
            ],
        }
        self.retrieval = self._valid_retrieval_scenarios()
        self._write_json()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_component(
        self, relative_path: str, name: str, description: str, body: str
    ) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        plugin_dir = self.repo / "/".join(relative_path.split("/")[:2])
        manifest = plugin_dir / ".claude-plugin/plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"name": plugin_dir.name, "version": "1.0.0"}),
            encoding="utf-8",
        )
        path.write_text(
            f'---\nname: {name}\ndescription: "{description}"\n---\n\n{body}',
            encoding="utf-8",
        )

    def _write_json(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.fixtures_path.write_text(json.dumps(self.fixtures), encoding="utf-8")
        self.retrieval_path.write_text(json.dumps(self.retrieval), encoding="utf-8")
        marketplace_path = self.repo / ".claude-plugin/marketplace.json"
        marketplace_path.parent.mkdir(parents=True, exist_ok=True)
        marketplace_path.write_text(
            json.dumps(self.marketplace),
            encoding="utf-8",
        )

    def _valid_retrieval_scenarios(self) -> dict:
        route_ids = list(catalog_quality.REQUIRED_ROUTE_KINDS)
        routes = {
            route_id: {
                "kind": kind,
                "plugin": "alpha",
                "tools": [f"{route_id}-tool"],
            }
            for route_id, kind in catalog_quality.REQUIRED_ROUTE_KINDS.items()
        }
        compositions = {
            name: {"step_variants": [["lexical", "semantic-rag"]]}
            for name in catalog_quality.REQUIRED_COMPOSITIONS
        }
        scenarios = []
        for index, route_id in enumerate(route_ids):
            near_route = route_ids[(index + 1) % len(route_ids)]
            scenarios.append(
                {
                    "id": f"{route_id}-contract",
                    "query": (
                        f"Evaluate the primary {route_id} retrieval contract "
                        f"for scenario number {index}."
                    ),
                    "corpus_cues": [f"{route_id} corpus cue"],
                    "expected": {
                        "route": route_id,
                        "plugins": ["alpha"],
                        "tools": [f"{route_id}-tool"],
                    },
                    "rationale": (
                        f"This scenario exercises the documented {route_id} route."
                    ),
                    "near_misses": [
                        {
                            "query": (
                                f"Evaluate the boundary alternative {near_route} "
                                f"for scenario number {index}."
                            ),
                            "expected_route": near_route,
                            "reason": (
                                f"The corpus cues instead require {near_route}."
                            ),
                        }
                    ],
                }
            )
        for index, name in enumerate(sorted(catalog_quality.REQUIRED_COMPOSITIONS)):
            scenarios.append(
                {
                    "id": f"{name}-contract",
                    "query": (
                        f"Evaluate the composed {name} retrieval contract "
                        f"for composition number {index}."
                    ),
                    "corpus_cues": [f"{name} composition cue"],
                    "expected": {
                        "route": "lexical",
                        "plugins": ["alpha"],
                        "tools": ["lexical-tool", "semantic-rag-tool"],
                        "composition": {
                            "name": name,
                            "steps": ["lexical", "semantic-rag"],
                        },
                    },
                    "rationale": (
                        f"This scenario exercises the documented {name} composition."
                    ),
                    "near_misses": [
                        {
                            "query": (
                                f"Evaluate the single-route alternative for "
                                f"composition number {index}."
                            ),
                            "expected_route": "lexical",
                            "reason": "The bounded query does not require composition.",
                        }
                    ],
                }
            )
        return {
            "schema_version": 1,
            "evaluation_boundary": catalog_quality.RETRIEVAL_EVALUATION_BOUNDARY,
            "routes": routes,
            "compositions": compositions,
            "scenarios": scenarios,
        }

    def _validate(self):
        self._write_json()
        return catalog_quality.validate_repository(
            self.repo,
            policy_path=self.policy_path,
            fixtures_path=self.fixtures_path,
            retrieval_scenarios_path=self.retrieval_path,
        )

    def test_valid_catalog_passes(self) -> None:
        result = self._validate()
        self.assertEqual([], result.errors)
        self.assertEqual(2, result.component_count)
        self.assertEqual(8, result.fixture_example_count)
        route_count = len(catalog_quality.REQUIRED_ROUTE_KINDS)
        composition_count = len(catalog_quality.REQUIRED_COMPOSITIONS)
        self.assertEqual(route_count, result.retrieval_route_count)
        self.assertEqual(composition_count, result.retrieval_composition_count)
        self.assertEqual(
            route_count + composition_count, result.retrieval_scenario_count
        )
        self.assertEqual(
            route_count + composition_count, result.retrieval_near_miss_count
        )

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

    def test_retrieval_schema_version_is_enforced(self) -> None:
        self.retrieval["schema_version"] = 2
        result = self._validate()
        self.assertTrue(
            any("`schema_version` must be 1" in error for error in result.errors),
            result.errors,
        )

    def test_retrieval_evaluation_boundary_is_canonical(self) -> None:
        self.retrieval["evaluation_boundary"] = (
            "This suite proves live-model routing accuracy."
        )
        result = self._validate()
        self.assertTrue(
            any(
                "`evaluation_boundary` must equal the canonical" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_invalid_scenario_shape_reports_valid_contract_counts(
        self,
    ) -> None:
        self.retrieval["routes"]["unexpected"] = {
            "kind": "modality",
            "plugin": "alpha",
            "tools": ["unexpected-tool"],
        }
        self.retrieval["compositions"]["unexpected"] = {
            "step_variants": [["lexical", "semantic-rag"]]
        }
        self.retrieval["scenarios"] = {}
        result = self._validate()
        self.assertEqual(
            len(catalog_quality.REQUIRED_ROUTE_KINDS),
            result.retrieval_route_count,
        )
        self.assertEqual(
            len(catalog_quality.REQUIRED_COMPOSITIONS),
            result.retrieval_composition_count,
        )

    def test_retrieval_route_and_composition_coverage_is_enforced(self) -> None:
        self.retrieval["scenarios"] = [
            scenario
            for scenario in self.retrieval["scenarios"]
            if scenario["expected"]["route"] != "metrics"
            and scenario["expected"].get("composition", {}).get("name")
            != "find-then-pin"
        ]
        result = self._validate()
        self.assertTrue(
            any("route `metrics` has no scenario" in error for error in result.errors),
            result.errors,
        )
        self.assertTrue(
            any(
                "composition `find-then-pin` has no scenario" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_unknown_plugin_and_tool_references_are_rejected(self) -> None:
        self.retrieval["routes"]["lexical"]["plugin"] = "missing-plugin"
        self.retrieval["scenarios"][0]["expected"]["tools"] = ["unknown-search-tool"]
        result = self._validate()
        self.assertTrue(
            any(
                "references unknown plugin `missing-plugin`" in error
                for error in result.errors
            ),
            result.errors,
        )
        self.assertTrue(
            any(
                "references unknown tool `unknown-search-tool`" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_plugin_must_be_listed_in_marketplace(self) -> None:
        manifest = self.repo / "plugins/gamma/.claude-plugin/plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"name": "gamma", "version": "1.0.0"}),
            encoding="utf-8",
        )
        self.retrieval["routes"]["lexical"]["plugin"] = "gamma"
        self.retrieval["scenarios"][0]["expected"]["plugins"] = ["gamma"]
        result = self._validate()
        self.assertTrue(
            any(
                "references unknown plugin `gamma`" in error for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_plugin_manifest_name_must_match_marketplace(self) -> None:
        manifest = self.repo / "plugins/alpha/.claude-plugin/plugin.json"
        manifest.write_text(
            json.dumps({"name": "renamed-alpha", "version": "1.0.0"}),
            encoding="utf-8",
        )
        result = self._validate()
        self.assertTrue(
            any(
                "manifest name `renamed-alpha` does not match `alpha`" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_composition_steps_must_match_contract(self) -> None:
        scenario = next(
            scenario
            for scenario in self.retrieval["scenarios"]
            if "composition" in scenario["expected"]
        )
        scenario["expected"]["composition"]["steps"] = ["lexical", "history"]
        scenario["expected"]["tools"] = ["lexical-tool", "history-tool"]
        result = self._validate()
        self.assertTrue(
            any("steps do not match contract" in error for error in result.errors),
            result.errors,
        )

    def test_retrieval_composition_step_variants_require_coverage(self) -> None:
        self.retrieval["compositions"]["hybrid-rerank"]["step_variants"].append(
            ["history", "semantic-rag"]
        )
        result = self._validate()
        self.assertTrue(
            any(
                "composition `hybrid-rerank` step variant "
                "['history', 'semantic-rag'] has no scenario" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_retrieval_near_misses_are_required_and_distinct(self) -> None:
        self.retrieval["scenarios"][0]["near_misses"] = []
        self.retrieval["scenarios"][1]["near_misses"][0]["expected_route"] = (
            self.retrieval["scenarios"][1]["expected"]["route"]
        )
        result = self._validate()
        self.assertTrue(
            any(
                "near_misses must be a non-empty array" in error
                for error in result.errors
            ),
            result.errors,
        )
        self.assertTrue(
            any(
                "expected_route must differ from the primary route" in error
                for error in result.errors
            ),
            result.errors,
        )


if __name__ == "__main__":
    unittest.main()
