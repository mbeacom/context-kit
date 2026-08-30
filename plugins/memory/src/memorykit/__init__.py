"""memorykit: provenance-bound durable memory records, validator, and MCP server.

Standard library only, by design. That property is what makes this unit
separable from the `memory` plugin at all (ADR-0002, ADR-0009): it installs and
runs with no plugin host, no bootstrap step, and nothing to resolve at runtime
except the interpreter it was invoked with.

Two entry points, one implementation:

``memorykit``       the CLI — validate, capture, search, review, record-state,
                    audit, doctor, and provider reconciliation.
``memorykit-mcp``   a stdio MCP server exposing recall/capture/review to an
                    agent harness. It shells out to the CLI rather than reusing
                    its internals in-process, so the two surfaces cannot drift.

# @adr 0006
# @adr 0009
"""

from __future__ import annotations

__version__ = "0.7.0"

__all__ = ["__version__"]
