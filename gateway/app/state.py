"""Shared in-memory state: the point store, the alarm engine, and the work order store.

`points` being a plain dict is enough: FastAPI's event loop is single-threaded and
cooperative, and every writer does a single atomic dict assignment with no `await` in
between, so there's no window for readers to see a half-written point. Trend history
(unlike current point values) does need to survive past "the latest poll," which is why
it's in SQLite (db.py) instead of here — this module only ever holds the live snapshot.

set_point()/fault_point()/fault_device() below are thin wrappers over points.py's
Point/publish/fault/fault_device — kept at the same names and call signatures so every
poller's call site (modbus_meter.py, bacnet_ahu.py, fire_panel.py, access_control.py)
is unchanged by points.py's existence. What changed is what `points` actually holds:
typed Point instances instead of untyped dicts, enforced by every consumer now reading
attributes instead of string keys (alarms.py, supervisor.py, main.py).
"""

from __future__ import annotations

from .alarms import AlarmEngine
from .points import Point, PointStatus, PointStore
from .points import fault as _fault
from .points import fault_device as _fault_device
from .points import publish as _publish
from .work_orders import WorkOrderStore

points: PointStore = {}
alarm_engine = AlarmEngine()
work_order_store = WorkOrderStore()


def set_point(
    point_id: str,
    device: str,
    name: str,
    value: float | str | None,
    units: str | None = None,
    status: PointStatus = "ok",
) -> None:
    _publish(
        points,
        Point(id=point_id, device=device, name=name, value=value, units=units, status=status),
    )


def fault_point(point_id: str, device: str, name: str, units: str | None = None) -> None:
    _fault(points, point_id, device, name, units)


def fault_device(device: str) -> None:
    _fault_device(points, device)
