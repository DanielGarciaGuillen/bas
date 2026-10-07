"""Shared in-memory state: the point store, the alarm engine, and the work order store.

`points` being a plain dict is enough: FastAPI's event loop is single-threaded and
cooperative, and every writer does a single atomic dict assignment with no `await` in
between, so there's no window for readers to see a half-written point. Trend history
(unlike current point values) does need to survive past "the latest poll," which is why
it's in SQLite (db.py) instead of here — this module only ever holds the live snapshot.
"""

from __future__ import annotations

from .alarms import AlarmEngine
from .work_orders import WorkOrderStore

points: dict[str, dict] = {}
alarm_engine = AlarmEngine()
work_order_store = WorkOrderStore()
