"""Real-CLI compatibility smoke test for the optional MemPalace provider.

This file is intentionally separate from ``test_memory_provider.py``. That
suite pins exact argv against a scripted fake executable so it always runs
deterministically offline; this file instead exercises a *real* installed
MemPalace CLI to catch drift the fakes cannot model on their own.

Every test here skips cleanly when MemPalace is not installed. The version
and capability-help checks are read-only, bounded, and cheap, so they run
automatically whenever the CLI is present. The tiny capture/search round
trip mutates a temporary, project-isolated palace and can depend on an
optional local backend, so it is opt-in via
``CONTEXT_KIT_MEMPALACE_LIVE_TEST=1``.

Nothing in this file touches a real user palace: every subprocess call sets
``MEMPALACE_PALACE_PATH`` to a directory under a fresh ``tempfile`` root that
is destroyed in ``tearDown``, mirroring how the adapter itself isolates each
configured project (see ``Config.palace_path`` in ``memory-provider.py``).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "memory-provider.py"
SPEC = importlib.util.spec_from_file_location("memory_provider_compat", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
memory_provider = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_provider
SPEC.loader.exec_module(memory_provider)


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _resolve_executable() -> str | None:
    override = _first_env("CONTEXT_KIT_MEMPALACE_BIN")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return override
    return shutil.which("mempalace")


EXECUTABLE = _resolve_executable()
LIVE_WRITE_OPT_IN = "CONTEXT_KIT_MEMPALACE_LIVE_TEST"


@unittest.skipUnless(
    EXECUTABLE,
    "MemPalace CLI is not installed; skipping the real-CLI compatibility "
    "smoke test (set CONTEXT_KIT_MEMPALACE_BIN or install `mempalace` to run it)",
)
class MemPalaceCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.palace = self.root / "palace"
        self.env = os.environ.copy()
        # Never let a live probe touch a developer's real palace.
        self.env["MEMPALACE_PALACE_PATH"] = str(self.palace)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(
        self,
        *argv: str,
        timeout: float = 20.0,
        input_bytes: bytes | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        assert EXECUTABLE is not None
        return subprocess.run(
            [EXECUTABLE, *argv],
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=self.env,
        )

    def test_version_reports_a_parseable_release(self) -> None:
        result = self.run_cli("--version")

        self.assertEqual(0, result.returncode, result.stderr.decode())
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        parsed = memory_provider._parse_mempalace_version(raw)
        self.assertIsNotNone(parsed, f"could not parse a version from: {raw!r}")
        status = memory_provider._mempalace_version_status(parsed)
        self.assertIn(status, {"tested", "older-than-tested", "newer-than-tested"})
        if status != "tested":
            print(
                f"NOTE: installed MemPalace {raw!r} is {status} relative to "
                "the "
                f"{memory_provider.MEMPALACE_TESTED_RELEASE_LINE} release "
                "line this adapter is tested against. Capability probes "
                "below still decide whether the adapter can use it safely.",
                file=sys.stderr,
            )

    def test_required_capability_surfaces_match_the_adapter_contract(self) -> None:
        # Mirrors `_doctor`'s capability probing, but against the real CLI
        # instead of the fake executable used in test_memory_provider.py.
        config = memory_provider.Config(
            provider="mempalace",
            home=self.root / "home",
            project="mbeacom/context-kit",
            auto_capture=False,
        )
        failures = [
            report
            for probe in memory_provider._required_mempalace_capabilities()
            if (
                report := memory_provider._probe_mempalace_capability(
                    EXECUTABLE, config, probe
                )
            )["status"]
            != "ok"
        ]

        self.assertEqual(
            [],
            failures,
            "installed MemPalace CLI does not satisfy the adapter's required "
            f"capability surfaces: {json.dumps(failures)}",
        )

    @unittest.skipUnless(
        _truthy(os.environ.get(LIVE_WRITE_OPT_IN)),
        f"set {LIVE_WRITE_OPT_IN}=1 to run the live capture/search smoke "
        "test against a temporary, project-isolated palace",
    )
    def test_tiny_capture_and_search_round_trip_on_an_isolated_palace(self) -> None:
        project_dir = self.root / "project"
        project_dir.mkdir()
        needle = "context-kit compatibility smoke test marker 8f2c1a"
        (project_dir / "note.txt").write_text(f"{needle}\n", encoding="utf-8")

        # `sqlite_exact` is a lexical, no-embedding backend: it avoids
        # downloading or loading an embedding model, so this stays fast and
        # offline. If the installed MemPalace does not support it, skip
        # instead of falling back to the default backend, which could
        # otherwise download a model as a side effect of running tests.
        mine = self.run_cli(
            "mine",
            str(project_dir),
            "--wing",
            "context-kit-compat-smoke",
            "--backend",
            "sqlite_exact",
            timeout=60.0,
        )
        if mine.returncode != 0:
            self.skipTest(
                "installed MemPalace could not mine with the sqlite_exact "
                "no-embedding backend: "
                f"{mine.stderr.decode('utf-8', errors='replace').strip()}"
            )

        search = self.run_cli(
            "search",
            needle,
            "--wing",
            "context-kit-compat-smoke",
            "--backend",
            "sqlite_exact",
            "--results",
            "1",
            timeout=30.0,
        )

        self.assertEqual(0, search.returncode, search.stderr.decode())
        self.assertIn(needle, search.stdout.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
