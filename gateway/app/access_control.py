"""Polls the access control sim (REST, same deliberate boundary as the fire panel) and
normalizes door states + the most recent event into points.

Unlike the fire panel, nothing here drives an interlock — forced/held-open doors just
raise a point the alarm engine (M6) will eventually act on. See docs/access-control-notes.md.
"""

from __future__ import annotations

import logging
import os

import httpx

from .points import Point, PointStore

log = logging.getLogger("gateway.access_control")

ACCESS_CONTROL_URL = os.environ.get("ACCESS_CONTROL_URL", "http://access-control:8002")
POLL_INTERVAL_S = float(os.environ.get("ACCESS_CONTROL_POLL_INTERVAL_S", "2"))
REQUEST_TIMEOUT_S = 5.0

_client: httpx.AsyncClient | None = None


def _client_handle() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=ACCESS_CONTROL_URL, timeout=REQUEST_TIMEOUT_S)
    return _client


async def read(known: PointStore) -> list[Point]:
    client = _client_handle()
    try:
        state_resp = await client.get("/state")
        state_resp.raise_for_status()
        state = state_resp.json()

        events_resp = await client.get("/events", params={"limit": 1})
        events_resp.raise_for_status()
        latest_events = events_resp.json()

        results = [
            Point(
                id=f"access-control.door{door['id']}",
                device="access-control",
                name=door["name"],
                value=door["state"].upper(),
            )
            for door in state["doors"]
        ]
        last_event_value = latest_events[0]["reason"] if latest_events else "—"
        results.append(
            Point(
                id="access-control.last_event",
                device="access-control",
                name="Last Event",
                value=last_event_value,
            )
        )
        return results
    except Exception:
        log.exception("Failed to poll access control at %s", ACCESS_CONTROL_URL)
        # Faults every door point already known (scanned from `known`, not a fixed door
        # count — a 4th door is covered here too) plus `last_event` unconditionally, so a
        # comms failure is visible from the very first failed poll even before any door
        # has ever been seen.
        faults = [
            Point(
                id=point_id, device=p.device, name=p.name, value=None, units=p.units, status="fault"
            )
            for point_id, p in known.items()
            if p.device == "access-control" and point_id != "access-control.last_event"
        ]
        faults.append(
            Point(
                id="access-control.last_event",
                device="access-control",
                name="Last Event",
                value=None,
                status="fault",
            )
        )
        return faults
