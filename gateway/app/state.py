"""Shared in-memory state: the point store, the alarm engine, and the work order store.

`points` being a plain dict is enough: FastAPI's event loop is single-threaded and
cooperative, and every writer does a single atomic dict assignment with no `await` in
between, so there's no window for readers to see a half-written point. Trend history
(unlike current point values) does need to survive past "the latest poll," which is why
it's in SQLite (db.py) instead of here — this module only ever holds the live snapshot.

Each poller publishes directly into `points` via poller.py's `run_poller()` shell now
(see points.py's `publish()`) — this module no longer owns any point-writing helpers
itself, just the shared store and the other two pieces of gateway-wide state.
"""

from __future__ import annotations

from .alarms import AlarmEngine
from .points import PointStore
from .work_orders import WorkOrderStore

points: PointStore = {}
alarm_engine = AlarmEngine()
work_order_store = WorkOrderStore()
