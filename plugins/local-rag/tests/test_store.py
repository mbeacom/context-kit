import sqlite3

import pytest

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


def test_chunk_ids_for_paths_handles_many_paths(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    # 1500 files (exceeds SQLite's 999-param limit) each with one chunk
    for i in range(1500):
        s.upsert_file(f"f{i}.md", "h", [_chunk(f"f{i}.md", "x")])
    paths = [f"f{i}.md" for i in range(1500)]
    ids = s.chunk_ids_for_paths(paths)
    assert len(ids) == 1500
    assert ids == sorted(ids)


def test_meta_kv(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.set_meta("model", "nomic-embed-text")
    s.set_meta("dim", "768")
    assert s.get_meta("model") == "nomic-embed-text"
    assert s.get_meta("dim") == "768"


def test_fts_backfill_and_chunk_lifecycle_sync(tmp_path):
    db_path = tmp_path / "meta.sqlite"
    # Simulate an index created before the FTS schema existed.
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE files (path TEXT PRIMARY KEY, file_hash TEXT NOT NULL);
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL, heading TEXT,
            start INTEGER, "end" INTEGER, text TEXT, tags TEXT, links TEXT
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO files VALUES ('a.md', 'old');
        INSERT INTO chunks(path, heading, start, "end", text, tags, links)
        VALUES ('a.md', 'A', 0, 12, 'legacy token', '[]', '[]');
        """
    )
    db.commit()
    db.close()

    s = MetaStore(db_path)
    s.init_schema()
    if not s.fts5_available:
        pytest.skip("SQLite was compiled without FTS5")
    assert s.lexical_search("legacy", 3)
    s.upsert_file("a.md", "new", [_chunk("a.md", "replacement token")])
    assert s.lexical_search("legacy", 3) == []
    assert s.lexical_search("replacement", 3)
    s.delete_file("a.md")
    assert s.lexical_search("replacement", 3) == []


def test_lexical_search_explains_missing_fts5(tmp_path):
    s = MetaStore(tmp_path / "meta.sqlite")
    s.init_schema()
    s.fts5_available = False
    with pytest.raises(RuntimeError, match="FTS5"):
        s.lexical_search("anything", 1)
