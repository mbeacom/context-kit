from local_rag.engine import Engine


class StubEmbedder:
    """Deterministic embedding by letter histogram (no network)."""

    model = "stub"
    DIM = 64

    def dim(self):
        return self.DIM

    def _vec(self, text):
        v = [0.0] * self.DIM
        for ch in text.lower():
            if ch.isalpha():
                v[(ord(ch) - 97) % self.DIM] += 1.0
        return v

    def embed(self, texts):
        return [self._vec(t) for t in texts]

    def close(self):
        pass


def _vault(tmp_path):
    (tmp_path / "apple.md").write_text("# Apple\n\nApples and oranges. #fruit\n")
    (tmp_path / "car.md").write_text("# Car\n\nEngines and wheels.\n")
    return tmp_path


def test_index_then_query(tmp_path):
    vault = _vault(tmp_path)
    data = tmp_path / "data"
    eng = Engine(name="t", data_dir=data, embedder=StubEmbedder())
    n = eng.index(vault)
    assert n["chunks"] >= 2
    hits = eng.query("apple orchard apples", k=2)
    assert hits and hits[0]["path"] == "apple.md"
    assert "heading" in hits[0] and "score" in hits[0]


def test_incremental_skip(tmp_path):
    vault = _vault(tmp_path)
    data = tmp_path / "data"
    eng = Engine(name="t", data_dir=data, embedder=StubEmbedder())
    eng.index(vault)
    second = eng.index(vault)
    assert second["indexed"] == 0 and second["skipped"] >= 2


def test_allowlist_paths(tmp_path):
    vault = _vault(tmp_path)
    data = tmp_path / "data"
    eng = Engine(name="t", data_dir=data, embedder=StubEmbedder())
    eng.index(vault)
    hits = eng.query("engine wheels", k=5, allowlist_paths=["car.md"])
    assert hits and all(h["path"] == "car.md" for h in hits)


def test_allowlist_normalizes_absolute_and_prefixed_paths(tmp_path):
    vault = _vault(tmp_path)
    data = tmp_path / "data"
    eng = Engine(name="t", data_dir=data, embedder=StubEmbedder())
    eng.index(vault)
    abs_path = str((vault / "car.md").resolve())  # absolute
    # absolute path should resolve to the stored relative key
    hits = eng.query("engine wheels", k=5, allowlist_paths=[abs_path])
    assert hits and all(h["path"] == "car.md" for h in hits)
    # basename-only should also resolve
    hits2 = eng.query("engine wheels", k=5, allowlist_paths=["car.md"])
    assert hits2 and all(h["path"] == "car.md" for h in hits2)
    # bogus path resolves to nothing (empty allowlist → no hits)
    hits3 = eng.query("engine", k=5, allowlist_paths=["/nope/missing.md"])
    assert hits3 == []


def test_reindex_changed_file_updates_results(tmp_path):
    vault = tmp_path / "v"
    vault.mkdir()
    data = tmp_path / "data"
    f = vault / "note.md"
    f.write_text("# Note\n\napple apple apple\n")
    eng = Engine(name="t", data_dir=data, embedder=StubEmbedder())
    eng.index(vault)
    f.write_text("# Note\n\nzebra zebra zebra\n")
    res = eng.index(vault)
    assert res["indexed"] == 1
    assert res.get("remove_failures", 0) == 0
    hits = eng.query("zebra zoo", k=3)
    assert hits and hits[0]["path"] == "note.md"
    assert "zebra" in hits[0]["snippet"]


def test_dim_mismatch_refused(tmp_path):
    import pytest

    vault = _vault(tmp_path)
    data = tmp_path / "data"
    Engine(name="t", data_dir=data, embedder=StubEmbedder()).index(vault)

    class Big(StubEmbedder):
        DIM = 128

    with pytest.raises(ValueError):
        Engine(name="t", data_dir=data, embedder=Big()).index(vault)
