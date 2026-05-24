from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .loaders.markdown import Chunk


class MetaStore:
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
