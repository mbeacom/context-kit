#!/usr/bin/env python3
"""Assert a build directory holds exactly the distributions a release expects.

This runs after ``uv build`` and before the artifacts are handed to the publish
job. Its job is narrow: catch a *distribution* that should not be published —
a stale wheel left from an earlier version, or a build backend that ignored the
declared version — while the tag can still be moved.

Why this is a script and not three lines of shell: the first version of this
check counted every regular file in ``dist/`` and so failed on ``uv build``'s
own ``dist/.gitignore``. That bug was invisible to review partly because the
step logged ``ls -l`` (which hides dotfiles) next to a ``find -type f`` count
(which does not), so the log showed two correct artifacts and then declared
them unexpected. Logic worth a regression test has to live somewhere a test can
call; a test that re-implemented the shell could pass while the workflow stayed
broken.

What counts as publishable is deliberately an allowlist — ``*.whl`` and
``*.tar.gz``. Anything else in the directory is build-tool bookkeeping, is
reported for visibility, and is not a release artifact. Note that only the
allowlist makes this safe in general: a stray *non-dotfile* would be picked up
by a ``dist/*`` glob downstream, and ``twine`` rejects a file it cannot parse
as a distribution.

Exit codes mirror ``scripts/release_version.py``: 0 = the directory holds
exactly the expected distributions; 1 = the check ran and something is wrong,
whether an artifact is missing, unexpected, or unreadable (all block a release,
so they share a code); 2 = the check could not run at all — bad arguments.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: Suffixes PyPI accepts as a distribution. Everything else in the build
#: directory is bookkeeping and is ignored rather than treated as an artifact.
DISTRIBUTION_SUFFIXES = (".whl", ".tar.gz")


def is_distribution(path: Path) -> bool:
    """Return whether ``path`` is a file PyPI would treat as a distribution."""
    return path.is_file() and path.name.endswith(DISTRIBUTION_SUFFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", required=True, help="directory uv build wrote to")
    parser.add_argument(
        "--package", required=True, help="distribution name, e.g. indexkit"
    )
    parser.add_argument("--version", required=True, help="version the tag asked for")
    args = parser.parse_args()

    dist_dir = Path(args.dist_dir)
    if not dist_dir.is_dir():
        print(f"ERROR: {dist_dir} is not a directory", file=sys.stderr)
        return 1

    expected = {
        f"{args.package}-{args.version}.tar.gz",
        f"{args.package}-{args.version}-py3-none-any.whl",
    }

    try:
        entries = sorted(dist_dir.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        print(f"ERROR: cannot read {dist_dir}: {exc}", file=sys.stderr)
        return 1

    found = {path.name for path in entries if is_distribution(path)}
    ignored = sorted(path.name for path in entries if not is_distribution(path))

    for name in sorted(expected):
        print(f"ok    {name}" if name in found else f"FAIL  {name}: missing")

    unexpected = sorted(found - expected)
    for name in unexpected:
        print(f"FAIL  {name}: unexpected distribution")

    # Reported, never fatal: build tools write their own bookkeeping here.
    for name in ignored:
        print(f"skip  {name}: not a distribution")

    missing = sorted(expected - found)
    if missing or unexpected:
        print()
        if missing:
            print(
                f"ERROR: {args.dist_dir} is missing: {', '.join(missing)}",
                file=sys.stderr,
            )
        if unexpected:
            print(
                f"ERROR: {args.dist_dir} holds distributions the tag did not ask "
                f"for: {', '.join(unexpected)}",
                file=sys.stderr,
            )
            print(
                "Publishing would upload them too. Clear the directory and "
                "rebuild; PyPI uploads cannot be replaced.",
                file=sys.stderr,
            )
        return 1

    print()
    print(
        f"OK: {args.dist_dir} holds exactly the {len(expected)} expected distributions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
