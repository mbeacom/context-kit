"""Packaging invariants for the `memorykit` distribution.

These assert properties that are cheap to break and expensive to discover late:
a stray import that only fails at a user's `pip install`, a version surface that
drifts, or a launcher that stops resolving. None of them need a build, an
installed distribution, or a network — they read the tree the way a build
backend would.

The stdlib-only assertion is the load-bearing one. ADR-0002 and ADR-0009 make
"pure standard library" the reason this unit is separable from its plugin at
all, and `pyproject.toml` declares no runtime dependencies. That declaration is
a promise the code can silently break, so it is checked rather than trusted.

# @adr 0009
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import sysconfig
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PLUGIN_ROOT / "src" / "memorykit"
PYPROJECT = PLUGIN_ROOT / "pyproject.toml"

MODULES = sorted(PACKAGE_ROOT.glob("*.py"))

# `sys.stdlib_module_names` is the interpreter's own answer and needs no
# allowlist to maintain. Available since 3.10, which is this package's floor.
STDLIB = set(sys.stdlib_module_names)


def _toplevel_imports(path: Path) -> set[str]:
    """Every distinct root module imported anywhere in a file.

    Includes imports nested inside functions and `try:` blocks, because an
    optional-looking deferred import is still a runtime dependency the moment
    the branch that needs it runs.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # `level > 0` is a relative import, which resolves inside this
            # package and cannot be a third-party dependency.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


class PurityTests(unittest.TestCase):
    def test_the_package_has_modules_to_check(self) -> None:
        # Guards the rest of this class: a glob that silently matched nothing
        # would make every assertion below vacuously true.
        self.assertTrue(MODULES, f"no modules found under {PACKAGE_ROOT}")

    def test_packaged_modules_import_only_the_standard_library(self) -> None:
        offenders: dict[str, set[str]] = {}
        for module in MODULES:
            external = {
                name
                for name in _toplevel_imports(module)
                if name not in STDLIB and name != "memorykit"
            }
            if external:
                offenders[module.name] = external
        self.assertEqual(
            offenders,
            {},
            "memorykit declares no runtime dependencies, and that property is "
            "why it is separable from the plugin at all (ADR-0002, ADR-0009). "
            "Either drop these imports or change the ADR on purpose: "
            f"{offenders}",
        )

    def test_pyproject_declares_no_runtime_dependencies(self) -> None:
        text = PYPROJECT.read_text(encoding="utf-8")
        match = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
        self.assertIsNotNone(match, "pyproject.toml has no [project].dependencies")
        assert match is not None
        body = re.sub(r"#.*", "", match.group(1)).strip()
        self.assertEqual(
            body,
            "",
            "the stdlib-only invariant is declared in pyproject.toml too; "
            f"found dependencies: {body!r}",
        )

    def test_the_package_imports_without_site_packages(self) -> None:
        """Import with `-S` and an empty PYTHONPATH, so nothing installed helps.

        A missing dependency would otherwise be invisible on a machine that
        happens to have it, which is exactly the machine this runs on.
        """
        stdlib = sysconfig.get_paths()["stdlib"]
        code = (
            "import sys; "
            f"sys.path = [{str(PACKAGE_ROOT.parent)!r}, {stdlib!r}, "
            f"{str(Path(stdlib) / 'lib-dynload')!r}]; "
            "import memorykit, memorykit.provider, memorykit.mcp; "
            "print(memorykit.__version__)"
        )
        result = subprocess.run(
            [sys.executable, "-S", "-c", code],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"import failed without site-packages:\n{result.stderr}",
        )
        # Deliberately not asserting a literal version. This test is about
        # import purity; the printed value only has to prove `__version__`
        # survived an import with no site-packages. Pinning the number here
        # would add a sixth version surface outside the five that
        # `scripts/release_version.py` reconciles, so the next bump would fail
        # this suite until someone hand-edited a test that is not about
        # versioning. `test_version_surfaces_agree` owns that check.
        self.assertRegex(
            result.stdout.strip(),
            r"^\d+\.\d+\.\d+",
            "memorykit.__version__ did not survive the site-packages-free import",
        )


class SurfaceTests(unittest.TestCase):
    def test_entry_points_resolve_to_real_callables(self) -> None:
        # A console script whose target does not exist installs fine and fails
        # only when a user runs it.
        text = PYPROJECT.read_text(encoding="utf-8")
        block = re.search(r"^\[project\.scripts\](.*?)(?=^\[|\Z)", text, re.M | re.S)
        self.assertIsNotNone(block, "pyproject.toml has no [project.scripts]")
        assert block is not None
        targets = dict(re.findall(r'^(\S+)\s*=\s*"([^"]+)"', block.group(1), re.M))
        self.assertEqual(
            set(targets),
            {"memorykit", "memorykit-mcp"},
            f"unexpected console scripts: {sorted(targets)}",
        )
        for script, target in targets.items():
            module_path, _, attribute = target.partition(":")
            source = PACKAGE_ROOT / f"{module_path.split('.', 1)[1]}.py"
            self.assertTrue(source.is_file(), f"{script} -> missing {source}")
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            names = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            self.assertIn(attribute, names, f"{script} -> {target} does not exist")

    def test_version_surfaces_agree(self) -> None:
        dunder = re.search(
            r"^__version__\s*=\s*\"([^\"]+)\"",
            (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"),
            re.M,
        )
        self.assertIsNotNone(dunder)
        assert dunder is not None
        project = re.search(
            r"^version\s*=\s*\"([^\"]+)\"",
            PYPROJECT.read_text(encoding="utf-8"),
            re.M,
        )
        self.assertIsNotNone(project)
        assert project is not None
        manifest = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]
        server = re.search(
            r'^SERVER_VERSION\s*=\s*"([^"]+)"',
            (PACKAGE_ROOT / "mcp.py").read_text(encoding="utf-8"),
            re.M,
        )
        self.assertIsNotNone(server)
        assert server is not None
        self.assertEqual(
            {dunder.group(1), project.group(1), server.group(1), manifest},
            {manifest},
            "package, MCP server, pyproject, and plugin versions disagree",
        )


class LauncherTests(unittest.TestCase):
    """The old paths are a published interface: hooks and `.mcp.json` name them."""

    LAUNCHERS = {
        PLUGIN_ROOT / "scripts" / "memory-provider.py": "provider.py",
        PLUGIN_ROOT / "mcp" / "server.py": "mcp.py",
    }

    def test_launchers_exist_where_hosts_expect_them(self) -> None:
        for launcher in self.LAUNCHERS:
            self.assertTrue(
                launcher.is_file(),
                f"{launcher} is referenced by hooks.json/.mcp.json and must exist",
            )

    def test_launchers_prefer_the_bundled_source(self) -> None:
        """Deliberately the reverse of the `indexkit` launcher (ADR-0009).

        The plugin's commands, hooks, and reference docs are written against the
        provider it ships with, so an installed `memorykit` of another version
        must not win.
        """
        for launcher in self.LAUNCHERS:
            text = launcher.read_text(encoding="utf-8")
            self.assertIn(
                "sys.path.insert(0",
                text,
                f"{launcher.name} must place the bundled src *ahead* of an "
                "installed distribution, not append it",
            )

    def test_launchers_actually_run(self) -> None:
        provider = PLUGIN_ROOT / "scripts" / "memory-provider.py"
        result = subprocess.run(
            [sys.executable, str(provider), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validate", result.stdout)
        # argparse derives prog from argv[0], so the launcher names itself
        # rather than the console script a plugin user does not have.
        self.assertIn("memory-provider.py", result.stdout)

    def test_mcp_launcher_refuses_arguments(self) -> None:
        server = PLUGIN_ROOT / "mcp" / "server.py"
        result = subprocess.run(
            [sys.executable, str(server), "unexpected"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("takes no arguments", result.stderr)


class HostWiringTests(unittest.TestCase):
    """Every host reference must name a path that exists after the move."""

    def test_hook_and_mcp_manifests_point_at_real_files(self) -> None:
        wiring = {
            PLUGIN_ROOT / "hooks" / "hooks.json": "scripts/memory-provider.py",
            PLUGIN_ROOT / ".mcp.json": "mcp/server.py",
        }
        for manifest, relative in wiring.items():
            if not manifest.is_file():
                continue
            text = manifest.read_text(encoding="utf-8")
            self.assertIn(
                relative,
                text,
                f"{manifest.name} no longer references {relative}",
            )
            self.assertTrue(
                (PLUGIN_ROOT / relative).is_file(),
                f"{manifest.name} references {relative}, which does not exist",
            )

    def test_mcp_manifest_declares_stdio_explicitly(self) -> None:
        config = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["context-kit-memory"]
        self.assertEqual("stdio", server["type"])
        self.assertEqual(
            {
                "CONTEXT_KIT_MEMORY_PROJECT": "${CONTEXT_KIT_MEMORY_PROJECT}",
                "PRODUCTIVITY_SKILLS_MEMORY_PROJECT": (
                    "${PRODUCTIVITY_SKILLS_MEMORY_PROJECT}"
                ),
            },
            server["env"],
        )


if __name__ == "__main__":
    unittest.main()
