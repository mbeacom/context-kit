from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .embed import OllamaEmbedder
from .engine import Engine, slug
from .storage import list_indexes, remove_index, validate_index_name


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _legacy_data_dir() -> Path:
    """Where a plugin install kept index data before standalone packaging.

    Kept resolvable so upgrading does not silently orphan existing indexes.
    """
    return Path.home() / ".claude/plugins/data/indexkit"


def _default_data_dir() -> Path:
    """Host-neutral default for a plain `pip install indexkit`.

    A user who installed from PyPI has no plugin host, so writing under
    `~/.claude/` would create a directory for an unrelated tool. Follow the XDG
    base-directory spec instead, honoring `XDG_DATA_HOME` when set.

    An existing plugin-managed directory still wins when the new location has
    not been created yet, so upgrading in place keeps working (ADR-0006).
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    default = (Path(xdg).expanduser() if xdg else Path.home() / ".local/share") / "indexkit"
    if not default.exists():
        legacy = _legacy_data_dir()
        if legacy.is_dir():
            return legacy
    return default


def _data_dir() -> Path:
    """Resolve where indexes live.

    Explicit configuration wins, then the host-provided plugin data directory,
    then a host-neutral default. `CLAUDE_PLUGIN_DATA` is set by the plugin host,
    so honoring it keeps plugin installs pointed at host-managed storage while a
    standalone install never touches it.
    """
    configured = _first_env("CONTEXT_KIT_DATA", "PRODUCTIVITY_SKILLS_DATA", "CLAUDE_PLUGIN_DATA")
    if configured:
        return Path(configured).expanduser()
    return _default_data_dir().expanduser()


def _make_embedder(args):
    model = (
        getattr(args, "model", None)
        or _first_env(
            "CONTEXT_KIT_EMBED_MODEL",
            "PRODUCTIVITY_SKILLS_EMBED_MODEL",
            "CLAUDE_PLUGIN_OPTION_EMBED_MODEL",
        )
        or "nomic-embed-text"
    )
    host = (
        _first_env(
            "CONTEXT_KIT_OLLAMA_HOST",
            "PRODUCTIVITY_SKILLS_OLLAMA_HOST",
            "CLAUDE_PLUGIN_OPTION_OLLAMA_HOST",
        )
        or "http://localhost:11434"
    )
    return OllamaEmbedder(
        model=model,
        host=host,
    )


def _name_for(args, corpus=None) -> str:
    if getattr(args, "name", None):
        return validate_index_name(args.name)
    return validate_index_name(slug(corpus) if corpus else "default")


def _index_name(value: str) -> str:
    try:
        return validate_index_name(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _read_allowlist(value) -> list[str] | None:
    if not value:
        return None
    if value == "-":
        return [ln.strip() for ln in sys.stdin if ln.strip()]
    lines = Path(value).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def _missing_index(name: str) -> str:
    return f"error: no index named '{name}'. Run 'rag index <path> --name {name}' first."


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(
        prog="indexkit",
        description="Hybrid semantic and lexical retrieval over a local index.",
    )
    # Exposed so an integrating adapter can pin/report a provider version the
    # same way it does for other retrieval backends.
    p.add_argument("--version", action="version", version=f"indexkit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index")
    pi.add_argument("path")
    pi.add_argument("--name", type=_index_name)
    pi.add_argument("--model")
    pi.add_argument("--include", action="append")
    pi.add_argument("--exclude", action="append")

    pq = sub.add_parser("query")
    pq.add_argument("text")
    pq.add_argument("--name", type=_index_name)
    pq.add_argument("--model")
    pq.add_argument("--k", type=int, default=10)
    pq.add_argument("--allowlist")
    pq.add_argument(
        "--hybrid",
        action="store_true",
        help="Fuse semantic and SQLite FTS5/BM25 candidates with reciprocal-rank fusion.",
    )
    pq.add_argument("--json", action="store_true")

    ps = sub.add_parser("status")
    ps.add_argument("--name", type=_index_name)
    ps.add_argument("--model")
    sub.add_parser("list")

    pr = sub.add_parser("remove")
    pr.add_argument("--name", required=True, type=_index_name)
    pr.add_argument(
        "--yes",
        action="store_true",
        help="Confirm non-interactive, permanent removal of the named index.",
    )

    args = p.parse_args(argv)
    data = _data_dir()

    if args.cmd == "list":
        for name in list_indexes(data):
            print(name)
        return 0

    if args.cmd == "remove":
        if not args.yes:
            print(
                f"error: refusing to remove index '{args.name}' without --yes",
                file=sys.stderr,
            )
            return 2
        try:
            removed = remove_index(data, args.name)
        except (OSError, RuntimeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"removed={args.name} artifacts={removed}")
        return 0

    if args.cmd == "index":
        eng = None
        try:
            eng = Engine(_name_for(args, args.path), data, _make_embedder(args))
            res = eng.index(args.path, args.include, args.exclude)
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        finally:
            if eng is not None:
                eng.close()
        print(
            f"indexed={res['indexed']} skipped={res['skipped']} "
            f"files={res['files']} chunks={res['chunks']}"
        )
        return 0

    if args.cmd == "status":
        name = _name_for(args)
        eng = None
        try:
            eng = Engine(name, data, _make_embedder(args), create=False)
            print(json.dumps(eng.store.stats()))
        except FileNotFoundError:
            print(_missing_index(name), file=sys.stderr)
            return 1
        except (OSError, RuntimeError, sqlite3.Error) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        finally:
            if eng is not None:
                eng.close()
        return 0

    if args.cmd == "query":
        name = _name_for(args)
        eng = None
        try:
            eng = Engine(name, data, _make_embedder(args), create=False)
            hits = eng.query(
                args.text,
                k=args.k,
                allowlist_paths=_read_allowlist(args.allowlist),
                hybrid=args.hybrid,
            )
        except FileNotFoundError:
            print(_missing_index(name), file=sys.stderr)
            return 1
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        finally:
            if eng is not None:
                eng.close()
        if args.json:
            print(json.dumps(hits))
        else:
            for h in hits:
                loc = f"{h['path']}" + (f" > {h['heading']}" if h["heading"] else "")
                snippet = h["snippet"].replace("\n", " ")
                score = f"[{h['score']:.3f}]"
                if h["retrieval_mode"] == "hybrid":
                    score = f"[{h['score']:.3f} hybrid]"
                print(f"{score} {loc}\n    {snippet}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
