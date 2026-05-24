from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .embed import OllamaEmbedder
from .engine import Engine, slug


def _data_dir() -> Path:
    return Path(
        os.environ.get("CLAUDE_PLUGIN_DATA", Path.home() / ".claude/plugins/data/local-rag")
    )


def _make_embedder(args):
    return OllamaEmbedder(
        model=args.model or os.environ.get("CLAUDE_PLUGIN_OPTION_EMBED_MODEL", "nomic-embed-text"),
        host=os.environ.get("CLAUDE_PLUGIN_OPTION_OLLAMA_HOST", "http://localhost:11434"),
    )


def _name_for(args, corpus=None) -> str:
    if getattr(args, "name", None):
        return args.name
    return slug(corpus) if corpus else "default"


def _read_allowlist(value) -> list[str] | None:
    if not value:
        return None
    if value == "-":
        return [ln.strip() for ln in sys.stdin if ln.strip()]
    return [ln.strip() for ln in Path(value).read_text().splitlines() if ln.strip()]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="rag", description="Local semantic RAG.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index")
    pi.add_argument("path")
    pi.add_argument("--name")
    pi.add_argument("--model")
    pi.add_argument("--include", action="append")
    pi.add_argument("--exclude", action="append")

    pq = sub.add_parser("query")
    pq.add_argument("text")
    pq.add_argument("--name")
    pq.add_argument("--model")
    pq.add_argument("--k", type=int, default=10)
    pq.add_argument("--allowlist")
    pq.add_argument("--tag", action="append")
    pq.add_argument("--json", action="store_true")

    ps = sub.add_parser("status")
    ps.add_argument("--name")
    ps.add_argument("--model")
    sub.add_parser("list")

    args = p.parse_args(argv)
    data = _data_dir()

    if args.cmd == "list":
        base = data / "indexes"
        for d in sorted(base.glob("*")) if base.exists() else []:
            print(d.name)
        return 0

    if args.cmd == "index":
        eng = Engine(_name_for(args, args.path), data, _make_embedder(args))
        try:
            res = eng.index(args.path, args.include, args.exclude)
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(
            f"indexed={res['indexed']} skipped={res['skipped']} "
            f"files={res['files']} chunks={res['chunks']}"
        )
        return 0

    if args.cmd == "status":
        eng = Engine(_name_for(args), data, _make_embedder(args))
        print(json.dumps(eng.store.stats()))
        return 0

    if args.cmd == "query":
        eng = Engine(_name_for(args), data, _make_embedder(args))
        try:
            hits = eng.query(args.text, k=args.k, allowlist_paths=_read_allowlist(args.allowlist))
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(hits))
        else:
            for h in hits:
                loc = f"{h['path']}" + (f" > {h['heading']}" if h["heading"] else "")
                print(f"[{h['score']:.3f}] {loc}\n    {h['snippet']}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
