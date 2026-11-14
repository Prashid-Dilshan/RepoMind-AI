"""Small SQLite registry of indexed repositories (survives restarts, shared by all requests)."""
import sqlite3
import time
from contextlib import contextmanager

from utils.config import DB_PATH

_COLUMNS = (
    "url", "name", "description", "language", "stars", "default_branch", "status", "stage",
    "error", "note", "files", "chunks", "created_at", "indexed_at", "last_used_at",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    repo_id        TEXT PRIMARY KEY,
    url            TEXT,
    name           TEXT,
    description    TEXT,
    language       TEXT,
    stars          INTEGER,
    default_branch TEXT,
    status         TEXT NOT NULL DEFAULT 'processing',
    stage          TEXT,
    error          TEXT,
    note           TEXT,
    files          INTEGER DEFAULT 0,
    chunks         INTEGER DEFAULT 0,
    created_at     REAL,
    indexed_at     REAL,
    last_used_at   REAL
)
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_SCHEMA)


def upsert(repo_id, **fields):
    unknown = set(fields) - set(_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown columns: {sorted(unknown)}")
    if not fields:
        return
    columns = ["repo_id", *fields]
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c}=excluded.{c}" for c in fields)
    sql = (
        f"INSERT INTO repos ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(repo_id) DO UPDATE SET {updates}"
    )
    with _connect() as conn:
        conn.execute(sql, [repo_id, *fields.values()])


def get(repo_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM repos WHERE repo_id = ?", (repo_id,)).fetchone()
    return dict(row) if row else None


def list_all():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM repos ORDER BY COALESCE(last_used_at, indexed_at, created_at) DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete(repo_id):
    with _connect() as conn:
        conn.execute("DELETE FROM repos WHERE repo_id = ?", (repo_id,))


def touch(repo_id):
    with _connect() as conn:
        conn.execute("UPDATE repos SET last_used_at = ? WHERE repo_id = ?", (time.time(), repo_id))


def count_processing():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM repos WHERE status = 'processing'").fetchone()[0]


def mark_interrupted():
    """Called at startup: anything still 'processing' was cut off by a restart."""
    with _connect() as conn:
        conn.execute(
            "UPDATE repos SET status = 'failed', error = ? WHERE status = 'processing'",
            ("Indexing was interrupted by a server restart. Index the repository again.",),
        )


def evictable(keep):
    """Repo ids beyond the `keep` most recently used ones (never includes repos being indexed)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT repo_id FROM repos WHERE status != 'processing' "
            "ORDER BY COALESCE(last_used_at, indexed_at, created_at) DESC"
        ).fetchall()
    return [r["repo_id"] for r in rows][keep:]
