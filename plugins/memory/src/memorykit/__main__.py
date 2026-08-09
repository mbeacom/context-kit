"""`python -m memorykit` — the same entry point as the `memorykit` console script.

Present so the package stays usable when a console script is not on PATH, which
is the normal situation inside a virtual environment invoked by absolute
interpreter path, or when a launcher runs `sys.executable -m memorykit`.
"""

from __future__ import annotations

from memorykit.provider import main

if __name__ == "__main__":
    raise SystemExit(main())
