"""Search history — locator queries persisted to SQLite under WORK_DIR.

Lets planners re-run earlier component searches ("history" in the UI).
SQLite keeps it dependency-free; swap for Firestore alongside the JobStore
when scaling out.
"""
import sqlite3
import time

from app.core.config import get_settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().work_dir / "history.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS searches ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts REAL NOT NULL,"
        " job_id TEXT NOT NULL,"
        " filename TEXT NOT NULL,"
        " query TEXT NOT NULL,"
        " hit_count INTEGER NOT NULL)"
    )
    return conn


def save_search(job_id: str, filename: str, query: str, hit_count: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO searches (ts, job_id, filename, query, hit_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), job_id, filename, query, hit_count),
        )


def list_searches(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, job_id, filename, query, hit_count FROM searches "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"ts": r[0], "job_id": r[1], "filename": r[2], "query": r[3], "hit_count": r[4]}
        for r in rows
    ]
