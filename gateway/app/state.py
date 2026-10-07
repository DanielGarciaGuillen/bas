"""Shared in-memory state: the point store, the alarm engine, and the work order store.

`points` being a plain dict is enough: FastAPI's event loop is single-threaded and
cooperative, and every writer does a single atomic dict assignment with no `await` in
between, so there's no window for readers to see a half-written point. Trend history
(unlike current point values) does need to survive past "the latest poll," which is why
it's in SQLite (db.py) instead of here — this module only ever holds the live snapshot.
"""

from __future__ import annotations

from typing import Literal

from .alarms import AlarmEngine
from .work_orders import WorkOrderStore

points: dict[str, dict] = {}
alarm_engine = AlarmEngine()
work_order_store = WorkOrderStore()


def set_point(
    point_id: str,
    device: str,
    name: str,
    value: float | str | None,
    units: str | None = None,
    status: Literal["ok", "fault"] = "ok",
) -> None:
    """The one place the six-key point shape gets written — every poller's success path
    used to hand-write this literal itself (eleven call sites, two per poller); a typo or
    a forgotten field in one poller had no way to surface except by comparing devices by
    eye."""
    points[point_id] = {
        "id": point_id,
        "device": device,
        "name": name,
        "value": value,
        "units": units,
        "status": status,
    }


def fault_point(point_id: str, device: str, name: str, units: str | None = None) -> None:
    """Mark one point faulted, even if it's never been successfully polled yet — used for
    the one point a poller guarantees it always publishes (e.g. a device's overall
    condition), so a failure is visible from the very first failed poll, not just once a
    point has existed at least once."""
    set_point(point_id, device, name, value=None, units=units, status="fault")


def fault_device(device: str) -> None:
    """Mark every point already known for this device as faulted. Before this existed,
    each poller's except-branch only re-wrote the one or two points it felt like repeating
    by hand — e.g. the access-control poller faulted `last_event` but left `door1`..`door3`
    showing their last good value tagged `status: "ok"` straight through an outage. This
    faults whatever this device has actually published so far, so a comms failure can't
    leave stale data looking current."""
    for point in points.values():
        if point["device"] == device:
            point["value"] = None
            point["status"] = "fault"
