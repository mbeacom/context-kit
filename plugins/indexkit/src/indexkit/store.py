from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .loaders.markdown import Chunk


class MetaStore:
    FTS_SCHEMA_VERSION = "1"

    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                heading TEXT,
                start INTEGER, "end" INTEGER,
                text TEXT,
                tags TEXT, links TEXT,
                FOREIGN KEY(path) REFERENCES files(path) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        try:
            self.db.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(text, content='chunks', content_rowid='id');
                CREATE TRIGGER IF NOT EXISTS chunks_fts_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_fts_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, text)
                    VALUES ('delete', old.id, old.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_fts_au AFTER UPDATE OF text ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, text)
                    VALUES ('delete', old.id, old.text);
                    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
                END;
                """
            )
        except sqlite3.OperationalError as error:
            if "fts5" not in str(error).lower():
                raise
            self.fts5_available = False
        else:
            self.fts5_available = True
            if self.get_meta("fts_schema_version") != self.FTS_SCHEMA_VERSION:
                self.db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
                self.db.execute(
                    "INSERT INTO meta(key, value) VALUES('fts_schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (self.FTS_SCHEMA_VERSION,),
                )
        self.db.commit()

    def file_hash(self, path: str) -> str | None:
        row = self.db.execute("SELECT file_hash FROM files WHERE path=?", (path,)).fetchone()
        return row["file_hash"] if row else None

    def upsert_file(self, path: str, file_hash: str, chunks: list[Chunk]) -> list[int]:
        cur = self.db.cursor()
        cur.execute("DELETE FROM chunks WHERE path=?", (path,))
        cur.execute(
            "INSERT INTO files(path, file_hash) VALUES(?,?) "
            "ON CONFLICT(path) DO UPDATE SET file_hash=excluded.file_hash",
            (path, file_hash),
        )
        ids: list[int] = []
        for c in chunks:
            cur.execute(
                'INSERT INTO chunks(path, heading, start, "end", text, tags, links) '
                "VALUES(?,?,?,?,?,?,?)",
                (
                    c.path,
                    c.heading,
                    c.start,
                    c.end,
                    c.text,
                    json.dumps(c.tags),
                    json.dumps(c.links),
                ),
            )
            ids.append(cur.lastrowid)
        self.db.commit()
        return ids

    def delete_file(self, path: str) -> None:
        self.db.execute("DELETE FROM chunks WHERE path=?", (path,))
        self.db.execute("DELETE FROM files WHERE path=?", (path,))
        self.db.commit()

    def lexical_search(
        self,
        text: str,
        k: int,
        allowlist: list[int] | None = None,
    ) -> list[tuple[int, float]]:
        """Return FTS5 BM25 candidates in stable rank order.

        BM25 scores are SQLite's native values (smaller is better); callers retain
        them as retrieval metadata rather than trying to compare them to vectors.
        """
        if not self.fts5_available:
            raise RuntimeError("SQLite FTS5 is unavailable; hybrid retrieval is not supported.")
        terms = re.findall(r"\w+", text, flags=re.UNICODE)
        if not terms or k <= 0:
            return []
        match = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        join = ""
        if allowlist is not None:
            if not allowlist:
                return []
            self.db.execute(
                "CREATE TEMP TABLE IF NOT EXISTS fts_allowlist (id INTEGER PRIMARY KEY)"
            )
            self.db.execute("DELETE FROM fts_allowlist")
            self.db.executemany(
                "INSERT INTO fts_allowlist(id) VALUES(?)",
                ((chunk_id,) for chunk_id in allowlist),
            )
            join = " JOIN fts_allowlist allowed ON allowed.id = chunks.id"
        rows = self.db.execute(
            """
            SELECT chunks.id, bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks ON chunks.id = chunks_fts.rowid
            """
            + join
            + """
            WHERE chunks_fts MATCH ?
            ORDER BY score ASC, chunks.id ASC
            LIMIT ?
            """,
            (match, k),
        ).fetchall()
        return [(row["id"], float(row["score"])) for row in rows]

    def chunk_ids_for_paths(self, paths: list[str]) -> list[int]:
        if not paths:
            return []
        ids: list[int] = []
        batch_size = 900
        for i in range(0, len(paths), batch_size):
            batch = paths[i : i + batch_size]
            qs = ",".join("?" * len(batch))
            rows = self.db.execute(f"SELECT id FROM chunks WHERE path IN ({qs})", batch).fetchall()
            ids.extend(r["id"] for r in rows)
        return sorted(ids)

    def get_chunk(self, chunk_id: int) -> dict:
        r = self.db.execute("SELECT * FROM chunks WHERE id=?", (chunk_id,)).fetchone()
        if not r:
            raise KeyError(chunk_id)
        return {
            "id": r["id"],
            "path": r["path"],
            "heading": r["heading"],
            "start": r["start"],
            "end": r["end"],
            "text": r["text"],
            "tags": json.loads(r["tags"]),
            "links": json.loads(r["links"]),
        }

    def all_paths(self) -> list[str]:
        return [r["path"] for r in self.db.execute("SELECT path FROM files ORDER BY path")]

    def stats(self) -> dict:
        files = self.db.execute("SELECT COUNT(*) c FROM files").fetchone()["c"]
        chunks = self.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
        return {
            "files": files,
            "chunks": chunks,
            "model": self.get_meta("model"),
            "dim": self.get_meta("dim"),
            "fts5": self.fts5_available,
        }

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.db.commit()

    def get_meta(self, key: str) -> str | None:
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

    def close(self) -> None:
        self.db.close()
