from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import ensure_dir


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                status TEXT NOT NULL,
                book_id TEXT DEFAULT '',
                pack_id TEXT DEFAULT '',
                mode TEXT NOT NULL,
                focus_topics TEXT NOT NULL,
                start_date TEXT NOT NULL,
                main_count INTEGER NOT NULL,
                short_count INTEGER NOT NULL,
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def create_upload_job(
    db_path: Path,
    *,
    filename: str,
    stored_path: str,
    mode: str,
    focus_topics: str,
    start_date: str,
    main_count: int,
    short_count: int,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO upload_jobs (
                filename, stored_path, status, book_id, pack_id, mode, focus_topics,
                start_date, main_count, short_count, error_message, created_at, updated_at
            ) VALUES (?, ?, 'queued', '', '', ?, ?, ?, ?, ?, '', ?, ?)
            """,
            (filename, stored_path, mode, focus_topics, start_date, main_count, short_count, now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_upload_job(db_path: Path, job_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]
    with connect(db_path) as conn:
        conn.execute(f"UPDATE upload_jobs SET {assignments} WHERE id = ?", values)
        conn.commit()


def get_upload_job(db_path: Path, job_id: int) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM upload_jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_upload_jobs(db_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM upload_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
