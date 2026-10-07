"""Point trend history — a plain SQLite table, per PLAN.md §5.3. No ORM: one table, two
indexed columns, and the stdlib's sqlite3 module is enough for a lab-scale, single-process
gateway. Writes happen off the event loop thread (asyncio.to_thread) since sqlite3 is
synchronous; reads are infrequent enough (one browser loading a trend chart) not to need
the same treatment, but get it anyway for consistency.

The database file lives inside the container and doesn't survive a rebuild — fine for a
demo lab, not a design that would survive a real deployment without a volume mount.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get("GATEWAY_DB_PATH", "/app/data/buildingops.db")

_connection: sqlite3.Connection | None = None


def _get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS point_history (
                point_id TEXT NOT NULL,
                value REAL NOT NULL,
                recorded_at TEXT NOT NULL
            )
            """
        )
        _connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_point_history_point_time "
            "ON point_history (point_id, recorded_at)"
        )
        _connection.commit()
    return _connection


def _record_samples_sync(samples: list[tuple[str, float, str]]) -> None:
    if not samples:
        return
    conn = _get_connection()
    conn.executemany(
        "INSERT INTO point_history (point_id, value, recorded_at) VALUES (?, ?, ?)", samples
    )
    conn.commit()


async def record_samples(samples: list[tuple[str, float, datetime]]) -> None:
    rows = [(point_id, value, recorded_at.isoformat()) for point_id, value, recorded_at in samples]
    await asyncio.to_thread(_record_samples_sync, rows)


def _query_history_sync(point_id: str, start: datetime, end: datetime, limit: int) -> list[dict]:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT value, recorded_at FROM point_history "
        "WHERE point_id = ? AND recorded_at >= ? AND recorded_at <= ? "
        "ORDER BY recorded_at ASC LIMIT ?",
        (point_id, start.isoformat(), end.isoformat(), limit),
    )
    return [{"value": row[0], "timestamp": row[1]} for row in cursor.fetchall()]


async def query_history(
    point_id: str, start: datetime, end: datetime, limit: int = 2000
) -> list[dict]:
    return await asyncio.to_thread(_query_history_sync, point_id, start, end, limit)
