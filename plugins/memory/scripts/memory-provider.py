#!/usr/bin/env python3
"""Launcher for the plugin deployment of the `memorykit` provider CLI.

The implementation moved to `src/memorykit/provider.py` when the contract,
validator, and MCP server were packaged for PyPI (ADR-0009). This path stays
because it is a published interface: `hooks/hooks.json`, `.mcp.json`, the slash
commands, and the skill references all invoke it by name, and a plugin update
must not break a host that already has those wired up.

**Resolution order is deliberately the reverse of `indexkit`'s launcher.** That
one prefers a bootstrapped venv and falls back to PATH, because its bundled
runtime may not exist. This plugin's bundled source always exists and is pure
standard library, so the vendored copy wins: the commands, hooks, and reference
docs shipped with plugin version X are written against provider version X, and
importing an unrelated `memorykit` that happens to be installed would run
different code than the surrounding plugin documents. An installed package is
used only if the vendored source is missing, which means a damaged deployment.

# @adr 0009
"""

from __future__ import annotations

import sys
from pathlib import Path

BUNDLED_SRC = Path(__file__).resolve().parents[1] / "src"


def _load_main():
    if (BUNDLED_SRC / "memorykit" / "provider.py").is_file():
        # Ahead of an installed distribution, not appended after it.
        sys.path.insert(0, str(BUNDLED_SRC))
    from memorykit.provider import main

    return main


if __name__ == "__main__":
    try:
        entry = _load_main()
    except ModuleNotFoundError as exc:  # pragma: no cover - damaged deployment
        print(
            f"memory: cannot load the memorykit provider ({exc}). Expected "
            f"{BUNDLED_SRC / 'memorykit' / 'provider.py'} to exist, or "
            "`memorykit` to be importable (pip install memorykit).",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    raise SystemExit(entry())
