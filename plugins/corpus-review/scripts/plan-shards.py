#!/usr/bin/env python3
"""Group inventory units into bounded, resumable review shards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

SCHEMA = "context-kit/corpus-shards-v1"
INVENTORY_SCHEMA = "context-kit/corpus-inventory-v1"
DEFAULT_MAX_BYTES = 200_000
DEFAULT_MAX_UNITS = 25


def inventory_digest(inventory: dict[str, Any]) -> str:
    """Hash the inventory's content rather than its file bytes.

    Volatile metadata such as `generated_at` is excluded, so re-running the
    inventory over an unchanged corpus yields the same digest and an in-flight
    review resumes instead of being invalidated by a timestamp. `root` is
    excluded too, so moving the corpus does not discard valid findings.
    """
    payload = {"scope": inventory.get("scope"), "units": inventory.get("units")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_inventory(path: Path) -> tuple[dict[str, Any], str]:
    """Return the parsed inventory and its content digest."""
    data = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("inventory must be a JSON object")
    if data.get("schema") != INVENTORY_SCHEMA:
        raise ValueError(f"inventory schema must be `{INVENTORY_SCHEMA}`")
    units = data.get("units")
    if not isinstance(units, list):
        raise ValueError("inventory `units` must be an array")
    return data, inventory_digest(data)


def shard_digest(units: Sequence[dict[str, Any]]) -> str:
    """Hash member unit hashes in order.

    The digest is the resumption key: a findings file is only reusable while
    its shard still contains exactly these units with exactly this content.
    """
    joined = "\n".join(str(unit.get("sha256")) for unit in units)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def shard_member(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": unit["id"],
        "path": unit["path"],
        "sha256": unit["sha256"],
        "bytes": unit["bytes"],
        "inspectable": unit["inspectable"],
        "range": unit.get("range"),
    }


def pack(
    units: Sequence[dict[str, Any]], max_bytes: int, max_units: int
) -> list[list[dict[str, Any]]]:
    """Greedily pack units in inventory order.

    Order is never rearranged for a tighter fit: adjacency usually reflects
    directory structure, which keeps a worker's brief coherent, and a stable
    order keeps shard ids reproducible across runs.
    """
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 0
    for unit in units:
        unit_bytes = int(unit["bytes"])
        if unit_bytes > max_bytes:
            if current:
                batches.append(current)
                current = []
                size = 0
            batches.append([unit])
            continue
        over_bytes = current and size + unit_bytes > max_bytes
        over_units = len(current) >= max_units
        if over_bytes or over_units:
            batches.append(current)
            current = []
            size = 0
        current.append(unit)
        size += unit_bytes
    if current:
        batches.append(current)
    return batches


def build_plan(
    inventory: dict[str, Any],
    inventory_sha256: str,
    max_bytes: int,
    max_units: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    units = [unit for unit in inventory["units"] if unit.get("in_scope")]
    shards = []
    for index, members in enumerate(pack(units, max_bytes, max_units), start=1):
        payload = [shard_member(unit) for unit in members]
        total = sum(int(member["bytes"]) for member in payload)
        shards.append(
            {
                "id": f"s{index:03d}",
                "digest": shard_digest(payload),
                "bytes": total,
                "oversized": len(payload) == 1 and total > max_bytes,
                "units": payload,
            }
        )

    generated = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "schema": SCHEMA,
        "generated_at": generated,
        "inventory_sha256": inventory_sha256,
        "budget": {"max_bytes": max_bytes, "max_units": max_units},
        "totals": {
            "shards": len(shards),
            "units": len(units),
            "bytes": sum(int(shard["bytes"]) for shard in shards),
            "oversized": sum(1 for shard in shards if shard["oversized"]),
        },
        "shards": shards,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="inventory JSON path")
    parser.add_argument("--out", required=True, help="shard plan JSON destination")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"byte budget per shard (default: {DEFAULT_MAX_BYTES})",
    )
    parser.add_argument(
        "--max-units",
        type=int,
        default=DEFAULT_MAX_UNITS,
        help=f"unit count ceiling per shard (default: {DEFAULT_MAX_UNITS})",
    )
    args = parser.parse_args(argv)

    if args.max_bytes <= 0 or args.max_units <= 0:
        print("ERROR: --max-bytes and --max-units must be positive", file=sys.stderr)
        return 2

    try:
        inventory, digest = load_inventory(Path(args.inventory).expanduser())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load inventory: {exc}", file=sys.stderr)
        return 2

    plan = build_plan(inventory, digest, args.max_bytes, args.max_units)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    totals = plan["totals"]
    print(
        f"Shard plan: {totals['shards']} shards over {totals['units']} units "
        f"({totals['bytes']} bytes) -> {out}"
    )
    if totals["oversized"]:
        print(
            f"WARNING: {totals['oversized']} shard(s) exceed the byte budget; "
            "subdivide those units with --max-unit-bytes at inventory time",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
