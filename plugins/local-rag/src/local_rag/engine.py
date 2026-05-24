from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .embed import OllamaEmbedder
from .index import VecIndex
from .loaders.markdown import iter_corpus, load_markdown
from .store import MetaStore


def slug(path) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(Path(path).resolve())).strip("-").lower()
    return s[-80:] or "default"


class Engine:
    def __init__(self, name: str, data_dir, embedder=None):
        self.name = name
        self.dir = Path(data_dir) / "indexes" / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or OllamaEmbedder()
        self.store = MetaStore(self.dir / "meta.sqlite")
        self.store.init_schema()
        self.index_path = self.dir / "index.tvim"

    def _dim(self) -> int:
        d = self.embedder.dim()
        stored = self.store.get_meta("dim")
        if stored is None:
            self.store.set_meta("dim", str(d))
            self.store.set_meta("model", self.embedder.model)
        elif int(stored) != d:
            raise ValueError(
                f"Embedding dim {d} (model '{self.embedder.model}') != index dim {stored} "
                f"(model '{self.store.get_meta('model')}'). Reindex with --name NEW or a matching model."
            )
        return d

    def _load_index(self, dim: int) -> VecIndex:
        if self.index_path.exists():
            return VecIndex.load(dim=dim, path=self.index_path)
        return VecIndex(dim=dim, path=self.index_path)

    def index(self, root, include=None, exclude=None) -> dict:
        dim = self._dim()
        idx = self._load_index(dim)
        root = Path(root)
        indexed = skipped = remove_failures = 0
        seen: set[str] = set()
        for fp in iter_corpus(root, include, exclude):
            rel = fp.relative_to(root).as_posix()
            seen.add(rel)
            raw = fp.read_text(encoding="utf-8", errors="replace")
            h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if self.store.file_hash(rel) == h:
                skipped += 1
                continue
            for cid in self.store.chunk_ids_for_paths([rel]):
                try:
                    idx.remove(cid)
                except Exception:
                    remove_failures += 1
            chunks = load_markdown(raw, rel)
            if not chunks:
                self.store.upsert_file(rel, h, [])
                continue
            vecs = self.embedder.embed([c.text for c in chunks])
            ids = self.store.upsert_file(rel, h, chunks)
            idx.add(ids, vecs)
            indexed += 1
        for gone in set(self.store.all_paths()) - seen:
            for cid in self.store.chunk_ids_for_paths([gone]):
                try:
                    idx.remove(cid)
                except Exception:
                    remove_failures += 1
            self.store.delete_file(gone)
        self.store.set_meta("root", str(Path(root).resolve()))
        idx.save()
        st = self.store.stats()
        return {
            "indexed": indexed,
            "skipped": skipped,
            "chunks": st["chunks"],
            "files": st["files"],
            "remove_failures": remove_failures,
        }

    def _normalize_allowlist(self, paths: list[str]) -> list[str]:
        """Map incoming file paths (absolute, $VAULT-prefixed, relative, or
        basename) to the corpus-relative keys used in the store."""
        stored = self.store.all_paths()
        have = set(stored)
        root_meta = self.store.get_meta("root")
        root = Path(root_meta) if root_meta else None
        out: list[str] = []
        for raw in paths:
            if raw in have:  # already a stored relative key
                out.append(raw)
                continue
            p = Path(raw)
            matched = False
            if root is not None:
                try:
                    rel = p.resolve().relative_to(root).as_posix()
                except ValueError:
                    rel = None
                if rel and rel in have:
                    out.append(rel)
                    matched = True
            if not matched:
                # basename fallback (handles $VAULT-relative prefixes)
                base = p.name
                for h in stored:
                    if h == base or Path(h).name == base or h.endswith("/" + base):
                        out.append(h)
                        matched = True
        # de-dup preserving order
        seen: set[str] = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def query(self, text: str, k: int = 10, allowlist_paths=None) -> list[dict]:
        dim = int(self.store.get_meta("dim") or self.embedder.dim())
        idx = self._load_index(dim)
        qv = self.embedder.embed([text])[0]
        allow = None
        if allowlist_paths:
            allow = self.store.chunk_ids_for_paths(self._normalize_allowlist(allowlist_paths))
        hits = idx.search(qv, k=k, allowlist=allow)
        out = []
        for cid, score in hits:
            try:
                ch = self.store.get_chunk(cid)
            except KeyError:
                continue
            out.append(
                {
                    "path": ch["path"],
                    "heading": ch["heading"],
                    "score": score,
                    "snippet": ch["text"][:240],
                }
            )
        return out
