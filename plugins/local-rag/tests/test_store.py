from local_rag.loaders.markdown import Chunk
from local_rag.store import MetaStore


def _chunk(path, text, heading="H"):
    return Chunk(
        text=text, path=path, heading=heading, start=0, end=len(text), tags=["t"], links=["L"]
    )


def test_upsert_returns_ids_and_lookup(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    ids = s.upsert_file("a.md", "hash1", [_chunk("a.md", "x"), _chunk("a.md", "y")])
    assert len(ids) == 2
    assert s.chunk_ids_for_paths(["a.md"]) == ids
    assert s.get_chunk(ids[0])["text"] == "x"
    assert s.get_chunk(ids[0])["tags"] == ["t"]


def test_content_hash_skip(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.upsert_file("a.md", "hash1", [_chunk("a.md", "x")])
    assert s.file_hash("a.md") == "hash1"


def test_reupsert_replaces_chunks(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.upsert_file("a.md", "h1", [_chunk("a.md", "x"), _chunk("a.md", "y")])
    new_ids = s.upsert_file("a.md", "h2", [_chunk("a.md", "z")])
    assert len(new_ids) == 1
    assert s.chunk_ids_for_paths(["a.md"]) == new_ids
    assert s.file_hash("a.md") == "h2"


def test_delete_and_stats(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.upsert_file("a.md", "h", [_chunk("a.md", "x")])
    s.upsert_file("b.md", "h", [_chunk("b.md", "y")])
    s.delete_file("a.md")
    assert s.all_paths() == ["b.md"]
    assert s.stats()["files"] == 1 and s.stats()["chunks"] == 1


def test_meta_kv(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.set_meta("model", "nomic-embed-text")
    s.set_meta("dim", "768")
    assert s.get_meta("model") == "nomic-embed-text"
    assert s.get_meta("dim") == "768"
