from __future__ import annotations

from pathlib import Path

import numpy as np
from turbovec import IdMapIndex


class VecIndex:
    """Thin wrapper around turbovec's ``IdMapIndex``.

    Isolates all turbovec-specific quirks (2-D batch queries, numpy
    dtypes, return shapes) so the rest of ``local_rag`` works with plain
    Python ``int``/``float`` ids and scores.
    """

    def __init__(self, dim: int, path) -> None:
        self.dim = dim
        self.path = Path(path)
        self._idx = IdMapIndex(dim=dim, bit_width=4)

    @classmethod
    def load(cls, dim: int, path) -> "VecIndex":
        obj = cls.__new__(cls)
        obj.dim = dim
        obj.path = Path(path)
        obj._idx = IdMapIndex.load(str(Path(path)))
        return obj

    def add(self, ids: list[int], vectors: list[list[float]]) -> None:
        v = np.asarray(vectors, dtype=np.float32)
        i = np.asarray(ids, dtype=np.uint64)
        self._idx.add_with_ids(v, i)

    def remove(self, chunk_id: int) -> None:
        self._idx.remove(int(chunk_id))

    def search(
        self,
        vector: list[float],
        k: int,
        allowlist: list[int] | None = None,
    ) -> list[tuple[int, float]]:
        # turbovec expects a 2-D (nq, dim) query and returns
        # (scores, ids) as (nq, effective_k) arrays. We submit a single
        # row and read row 0 back.
        q = np.asarray([vector], dtype=np.float32)
        if allowlist is not None:
            if not allowlist:
                return []
            allow = np.asarray(allowlist, dtype=np.uint64)
            scores, ids = self._idx.search(q, k=k, allowlist=allow)
        else:
            scores, ids = self._idx.search(q, k=k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._idx.write(str(self.path))
