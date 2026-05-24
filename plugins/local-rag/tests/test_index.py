import random

from local_rag.index import VecIndex


def _vec(seed, dim=64):
    r = random.Random(seed)
    return [r.random() for _ in range(dim)]


def test_add_search_roundtrip(tmp_path):
    idx = VecIndex(dim=64, path=tmp_path / "i.tvim")
    idx.add([10, 20, 30], [_vec(10), _vec(20), _vec(30)])
    hits = idx.search(_vec(20), k=3)
    assert hits[0][0] == 20
    assert all(isinstance(i, int) for i, _ in hits)


def test_allowlist_restricts(tmp_path):
    idx = VecIndex(dim=64, path=tmp_path / "i.tvim")
    idx.add([1, 2, 3, 4], [_vec(1), _vec(2), _vec(3), _vec(4)])
    hits = idx.search(_vec(3), k=4, allowlist=[1, 2])
    returned = {i for i, _ in hits}
    assert returned <= {1, 2}


def test_save_load(tmp_path):
    p = tmp_path / "i.tvim"
    idx = VecIndex(dim=64, path=p)
    idx.add([7], [_vec(7)])
    idx.save()
    idx2 = VecIndex.load(dim=64, path=p)
    hits = idx2.search(_vec(7), k=1)
    assert hits[0][0] == 7
