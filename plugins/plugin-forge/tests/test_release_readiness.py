from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "plugins/plugin-forge/scripts/release_readiness.py"
SPEC = importlib.util.spec_from_file_location("release_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
release_readiness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_readiness
SPEC.loader.exec_module(release_readiness)


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.plugins: list[dict[str, str]] = []

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_catalog(self) -> None:
        path = self.repo / ".claude-plugin/marketplace.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"name": "test-marketplace", "plugins": self.plugins}),
            encoding="utf-8",
        )

    def _write_plugin(
        self,
        name: str,
        *,
        version: str = "1.2.3",
        dependencies: tuple[str, ...] = (),
        apm_dependencies: tuple[str, ...] | None = None,
        changelog_version: str | None = None,
    ) -> Path:
        directory = self.repo / "plugins" / name
        manifest_path = directory / ".claude-plugin/plugin.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
            "name": name,
            "displayName": name.title(),
            "version": version,
            "description": f"The {name} test plugin.",
            "author": {"name": "Test Author"},
            "homepage": "https://example.com/test",
            "repository": "https://example.com/test.git",
            "license": "MIT",
            "keywords": ["test", name],
        }
        if dependencies:
            manifest["dependencies"] = list(dependencies)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        apm_lines = [
            f"name: {name}",
            f"version: {version}",
            f"description: The {name} test plugin.",
            "author: Test Author",
            "license: MIT",
            "homepage: https://example.com/test",
            "repository: https://example.com/test.git",
            f"keywords: [test, {name}]",
        ]
        effective_apm_dependencies = (
            dependencies if apm_dependencies is None else apm_dependencies
        )
        if effective_apm_dependencies:
            apm_lines.extend(["", "dependencies:", "  apm:"])
            apm_lines.extend(
                f"    - path: ../{dependency}"
                for dependency in effective_apm_dependencies
            )
        (directory / "apm.yml").write_text(
            "\n".join(apm_lines) + "\n", encoding="utf-8"
        )
        (directory / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (directory / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        release = changelog_version or version
        (directory / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {release} — 2026-07-19\n\n- Test release.\n",
            encoding="utf-8",
        )
        skill = directory / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"# {name}\n", encoding="utf-8")
        self.plugins.append(
            {
                "name": name,
                "source": f"./plugins/{name}",
                "description": f"The {name} test plugin.",
                "category": "test",
                "tags": ["test"],
            }
        )
        return directory

    def _validate(self):
        self._write_catalog()
        return release_readiness.validate_repository(self.repo)

    def test_valid_catalog_and_dependency_closure_pass(self) -> None:
        self._write_plugin("gamma")
        self._write_plugin("beta", dependencies=("gamma",))
        self._write_plugin("alpha", dependencies=("beta",))

        result = self._validate()

        self.assertEqual([], result.errors)
        self.assertEqual(3, result.plugin_count)
        self.assertEqual(2, result.dependency_edge_count)

    def test_missing_release_asset_and_metadata_are_reported(self) -> None:
        directory = self._write_plugin("alpha")
        (directory / "LICENSE").unlink()
        manifest_path = directory / ".claude-plugin/plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["repository"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = self._validate()

        self.assertTrue(
            any("missing or empty `LICENSE`" in error for error in result.errors),
            result.errors,
        )
        self.assertTrue(
            any(
                "`repository` must be a non-empty string" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_empty_manifest_is_validated_instead_of_silently_skipped(self) -> None:
        directory = self._write_plugin("alpha")
        (directory / ".claude-plugin/plugin.json").write_text(
            "{}",
            encoding="utf-8",
        )

        result = self._validate()

        self.assertTrue(
            any(
                "`$schema` must be a non-empty string" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_latest_changelog_release_must_match_manifest(self) -> None:
        self._write_plugin("alpha", version="2.0.0", changelog_version="1.9.0")

        result = self._validate()

        self.assertTrue(
            any(
                "latest release is 1.9.0, but plugin.json is 2.0.0" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_malformed_newest_changelog_release_is_not_skipped(self) -> None:
        directory = self._write_plugin("alpha", version="1.0.0")
        (directory / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## 2.0.0\n\n"
            "- Malformed new release.\n\n"
            "## 1.0.0 — 2026-07-19\n\n"
            "- Older valid release.\n",
            encoding="utf-8",
        )

        result = self._validate()

        self.assertTrue(
            any(
                "malformed latest release heading `## 2.0.0`" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_prefixed_newest_changelog_release_is_not_skipped(self) -> None:
        directory = self._write_plugin("alpha", version="1.0.0")
        (directory / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## v2.0.0 — 2026-07-19\n\n"
            "- Malformed new release.\n\n"
            "## 1.0.0 — 2026-07-19\n\n"
            "- Older valid release.\n",
            encoding="utf-8",
        )

        result = self._validate()

        self.assertTrue(
            any(
                "malformed latest release heading `## v2.0.0 — 2026-07-19`" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_unreleased_and_fenced_headings_do_not_hide_latest_release(self) -> None:
        directory = self._write_plugin("alpha", version="1.0.0")
        (directory / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "```markdown\n"
            "## example\n"
            "```\n\n"
            "## 1.0.0 – 2026-07-19\n\n"
            "- Valid release with an en dash.\n",
            encoding="utf-8",
        )

        result = self._validate()

        self.assertEqual([], result.errors)

    def test_direct_and_transitive_dependency_mismatches_are_reported(self) -> None:
        self._write_plugin("gamma")
        self._write_plugin(
            "beta",
            dependencies=("gamma",),
            apm_dependencies=(),
        )
        self._write_plugin("alpha", dependencies=("beta",))

        result = self._validate()

        self.assertTrue(
            any(
                "plugin `beta`: dependency mismatch" in error for error in result.errors
            ),
            result.errors,
        )
        self.assertTrue(
            any(
                "plugin `alpha`: dependency closure mismatch" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_unshipped_dependency_and_apm_path_are_reported(self) -> None:
        self._write_plugin(
            "alpha",
            dependencies=("missing",),
            apm_dependencies=("missing",),
        )

        result = self._validate()

        self.assertTrue(
            any("is not a shipped catalog plugin" in error for error in result.errors),
            result.errors,
        )
        self.assertTrue(
            any(
                "does not resolve to a shipped catalog plugin" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_dependency_cycles_are_reported_for_both_manifests(self) -> None:
        self._write_plugin("alpha", dependencies=("beta",))
        self._write_plugin("beta", dependencies=("alpha",))

        result = self._validate()

        self.assertTrue(
            any(
                "plugin.json: dependency cycle detected: alpha -> beta -> alpha"
                in error
                for error in result.errors
            ),
            result.errors,
        )
        self.assertTrue(
            any(
                "apm.yml: dependency cycle detected: alpha -> beta -> alpha" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_nested_apm_dependency_is_rejected(self) -> None:
        self._write_plugin("beta")
        directory = self._write_plugin("alpha", dependencies=("beta",))
        apm_path = directory / "apm.yml"
        apm_path.write_text(
            apm_path.read_text(encoding="utf-8").replace(
                "  apm:\n    - path: ../beta",
                "  apm:\n    group:\n      - path: ../beta",
            ),
            encoding="utf-8",
        )

        result = self._validate()

        self.assertTrue(
            any(
                "dependencies.apm must contain only direct" in error
                for error in result.errors
            ),
            result.errors,
        )

    def test_invalid_semantic_versions_are_rejected(self) -> None:
        for version in (
            "1.0.0-.",
            "1.0.0-alpha..1",
            "1.0.0-01",
            "1.0.0+build..1",
            "1٠.0.0",
        ):
            with self.subTest(version=version):
                self.assertFalse(release_readiness._is_semver(version))

    def test_invalid_catalog_json_fails_without_attribute_error(self) -> None:
        catalog = self.repo / ".claude-plugin/marketplace.json"
        catalog.parent.mkdir(parents=True, exist_ok=True)
        catalog.write_text("not-json", encoding="utf-8")

        result = release_readiness.validate_repository(self.repo)

        self.assertTrue(
            any("cannot load JSON" in error for error in result.errors),
            result.errors,
        )

    def test_catalog_source_cannot_escape_plugins_directory(self) -> None:
        self.plugins.append(
            {
                "name": "escape",
                "source": "../escape",
                "description": "Invalid source.",
                "category": "test",
                "tags": ["test"],
            }
        )

        result = self._validate()

        self.assertTrue(
            any(
                "source must resolve directly under `plugins/`" in error
                for error in result.errors
            ),
            result.errors,
        )


if __name__ == "__main__":
    unittest.main()
