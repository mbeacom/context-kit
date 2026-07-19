from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .embed import OllamaEmbedder
from .index import VecIndex
from .loaders.markdown import iter_corpus, load_markdown
from .storage import ensure_index_dir
from .store import MetaStore

RRF_K = 60
SEMANTIC_RRF_WEIGHT = 1.0
LEXICAL_RRF_WEIGHT = 1.0
HYBRID_CANDIDATE_MULTIPLIER = 3


def slug(path) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(Path(path).resolve())).strip("-").lower()
    return s[-80:] or "default"


def reciprocal_rank_fusion(
    semantic_hits: list[tuple[int, float]],
    lexical_hits: list[tuple[int, float]],
) -> list[dict]:
    """Fuse ranked sources with ``weight / (RRF_K + rank)``.

    The returned order breaks equal RRF scores by best source rank, then chunk id,
    making fusion reproducible even when a source assigns equal scores.
    """
    candidates: dict[int, dict] = {}
    for rank, (chunk_id, score) in enumerate(semantic_hits, start=1):
        hit = candidates.setdefault(chunk_id, {"id": chunk_id})
        hit["semantic_rank"] = rank
        hit["semantic_score"] = score
    for rank, (chunk_id, score) in enumerate(lexical_hits, start=1):
        hit = candidates.setdefault(chunk_id, {"id": chunk_id})
        hit["lexical_rank"] = rank
        hit["lexical_score"] = score
    for hit in candidates.values():
        hit["fused_score"] = (
            SEMANTIC_RRF_WEIGHT / (RRF_K + hit["semantic_rank"]) if "semantic_rank" in hit else 0.0
        ) + (LEXICAL_RRF_WEIGHT / (RRF_K + hit["lexical_rank"]) if "lexical_rank" in hit else 0.0)
    return sorted(
        candidates.values(),
        key=lambda hit: (
            -hit["fused_score"],
            min(hit.get("semantic_rank", float("inf")), hit.get("lexical_rank", float("inf"))),
            hit["id"],
        ),
    )


class Engine:
    def __init__(self, name: str, data_dir, embedder=None):
        self.name = name
        self.dir = ensure_index_dir(data_dir, name)
        self.embedder = embedder or OllamaEmbedder()
        self.store = MetaStore(self.dir / "meta.sqlite")
        self.store.init_schema()
        self.index_path = self.dir / "index.tvim"

    def close(self) -> None:
        try:
            self.store.close()
        finally:
            self.embedder.close()

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

    @staticmethod
    def _result(
        ch: dict,
        *,
        score: float,
        retrieval_mode: str,
        semantic_rank: int | None = None,
        semantic_score: float | None = None,
        lexical_rank: int | None = None,
        lexical_score: float | None = None,
        fused_rank: int | None = None,
        fused_score: float | None = None,
    ) -> dict:
        return {
            "path": ch["path"],
            "heading": ch["heading"],
            "score": score,
            "snippet": ch["text"][:240],
            "start": ch["start"],
            "end": ch["end"],
            "retrieval_mode": retrieval_mode,
            "semantic_rank": semantic_rank,
            "semantic_score": semantic_score,
            "lexical_rank": lexical_rank,
            "lexical_score": lexical_score,
            "fused_rank": fused_rank,
            "fused_score": fused_score,
        }

    def query(
        self, text: str, k: int = 10, allowlist_paths=None, hybrid: bool = False
    ) -> list[dict]:
        if k <= 0:
            return []
        if hybrid and not self.store.fts5_available:
            raise RuntimeError("SQLite FTS5 is unavailable; --hybrid cannot be used.")
        dim = int(self.store.get_meta("dim") or self.embedder.dim())
        idx = self._load_index(dim)
        qv = self.embedder.embed([text])[0]
        allow = None
        if allowlist_paths is not None:
            allow = self.store.chunk_ids_for_paths(self._normalize_allowlist(allowlist_paths))
        candidate_depth = k * HYBRID_CANDIDATE_MULTIPLIER if hybrid else k
        semantic_hits = idx.search(qv, k=candidate_depth, allowlist=allow)
        if hybrid:
            lexical_hits = self.store.lexical_search(text, k=candidate_depth, allowlist=allow)
            fused_hits = reciprocal_rank_fusion(semantic_hits, lexical_hits)[:k]
            out = []
            for fused_rank, hit in enumerate(fused_hits, start=1):
                try:
                    ch = self.store.get_chunk(hit["id"])
                except KeyError:
                    continue
                out.append(
                    self._result(
                        ch,
                        score=hit["fused_score"],
                        retrieval_mode="hybrid",
                        semantic_rank=hit.get("semantic_rank"),
                        semantic_score=hit.get("semantic_score"),
                        lexical_rank=hit.get("lexical_rank"),
                        lexical_score=hit.get("lexical_score"),
                        fused_rank=fused_rank,
                        fused_score=hit["fused_score"],
                    )
                )
            return out
        out = []
        for semantic_rank, (cid, score) in enumerate(semantic_hits, start=1):
            try:
                ch = self.store.get_chunk(cid)
            except KeyError:
                continue
            out.append(
                self._result(
                    ch,
                    score=score,
                    retrieval_mode="semantic",
                    semantic_rank=semantic_rank,
                    semantic_score=score,
                )
            )
        return out
