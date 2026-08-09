#!/usr/bin/env python3
"""Launcher for the plugin deployment of the `memorykit` stdio MCP server.

The implementation moved to `src/memorykit/mcp.py` when it was packaged for
PyPI (ADR-0009). This path stays because `.mcp.json` names it, and an installed
host has that wiring already.

Resolution order matches `scripts/memory-provider.py`: the vendored source wins
over any installed `memorykit`, so the server and the provider it shells out to
are always the same version. See that file for why this is the reverse of the
`indexkit` launcher's preference.

# @adr 0009
"""

from __future__ import annotations

import sys
from pathlib import Path

BUNDLED_SRC = Path(__file__).resolve().parents[1] / "src"


def _load_main():
    if (BUNDLED_SRC / "memorykit" / "mcp.py").is_file():
        sys.path.insert(0, str(BUNDLED_SRC))
    from memorykit.mcp import main

    return main


if __name__ == "__main__":
    try:
        entry = _load_main()
    except ModuleNotFoundError as exc:  # pragma: no cover - damaged deployment
        print(
            f"memory: cannot load the memorykit MCP server ({exc}). Expected "
            f"{BUNDLED_SRC / 'memorykit' / 'mcp.py'} to exist, or `memorykit` "
            "to be importable (pip install memorykit).",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    raise SystemExit(entry())
