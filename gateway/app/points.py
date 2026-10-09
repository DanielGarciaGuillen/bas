"""The one normalized point shape every poller publishes and every consumer reads.

Every protocol (BACnet, Modbus, the fire-panel/access-control REST sims) normalizes into
this same shape before it reaches the alarm engine, trend history, or the console — see
docs/architecture.md's "Point model" section. Before this module existed, the shape was a
convention enforced only by four pollers independently agreeing to write the same six
keys (gateway/app/state.py's set_point()/fault_point()/fault_device() closed the literal
duplication in M6's tactical pass — #12 — but every *consumer* still read it back out as
an untyped dict, re-deriving meaning from string keys: alarms.py compared display labels,
supervisor.py reverse-engineered "is this trendable" with an isinstance check).

Kept dependency-free and pure, same as alarms.py/work_orders.py: no FastAPI, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PointStatus = Literal["ok", "fault"]


@dataclass
class Point:
    id: str
    device: str
    name: str
    value: float | str | None
    units: str | None = None
    status: PointStatus = "ok"


PointStore = dict[str, Point]


def publish(store: PointStore, point: Point) -> None:
    store[point.id] = point


def fault(
    store: PointStore, point_id: str, device: str, name: str, units: str | None = None
) -> None:
    """Mark one point faulted, even if it's never been successfully published yet — used
    for the one point a poller guarantees it always publishes (e.g. a device's overall
    condition), so a failure is visible from the very first failed poll."""
    publish(
        store, Point(id=point_id, device=device, name=name, value=None, units=units, status="fault")
    )


def fault_device(store: PointStore, device: str) -> None:
    """Mark every point already known for this device as faulted, preserving each
    point's name/units. A comms failure can't leave stale data looking current — see the
    M6/#12 history on why a narrower per-point fault path isn't enough."""
    for point in list(store.values()):
        if point.device == device:
            publish(
                store,
                Point(
                    id=point.id,
                    device=point.device,
                    name=point.name,
                    value=None,
                    units=point.units,
                    status="fault",
                ),
            )


def numeric_points(store: PointStore) -> list[Point]:
    """The supervisor's predicate for "is this trendable" — isinstance-checking a dict's
    `.get("value")` used to live inline in supervisor.py; it's the one place that
    predicate is defined now."""
    return [p for p in store.values() if isinstance(p.value, (int, float))]
