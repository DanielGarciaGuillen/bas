"""Polls the access control sim (REST, same deliberate boundary as the fire panel) and
normalizes door states + the most recent event into points.

Unlike the fire panel, nothing here drives an interlock — forced/held-open doors just
raise a point the alarm engine (M6) will eventually act on. See docs/access-control-notes.md.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from .state import fault_device, fault_point, set_point

log = logging.getLogger("gateway.access_control")

ACCESS_CONTROL_URL = os.environ.get("ACCESS_CONTROL_URL", "http://access-control:8002")
POLL_INTERVAL_S = float(os.environ.get("ACCESS_CONTROL_POLL_INTERVAL_S", "2"))
REQUEST_TIMEOUT_S = 5.0


async def poll_access_control_forever() -> None:
    async with httpx.AsyncClient(base_url=ACCESS_CONTROL_URL, timeout=REQUEST_TIMEOUT_S) as client:
        while True:
            try:
                state_resp = await client.get("/state")
                state_resp.raise_for_status()
                state = state_resp.json()

                events_resp = await client.get("/events", params={"limit": 1})
                events_resp.raise_for_status()
                latest_events = events_resp.json()

                for door in state["doors"]:
                    point_id = f"access-control.door{door['id']}"
                    set_point(point_id, "access-control", door["name"], door["state"].upper())

                last_event_value = latest_events[0]["reason"] if latest_events else "—"
                set_point(
                    "access-control.last_event", "access-control", "Last Event", last_event_value
                )
            except Exception:
                log.exception("Failed to poll access control at %s", ACCESS_CONTROL_URL)
                # Faults every door point already known (previously only last_event was
                # faulted, leaving doors showing a stale value tagged status "ok" through
                # an outage) plus last_event explicitly, so a comms failure is visible
                # from the very first failed poll even before any door has ever been seen.
                fault_device("access-control")
                fault_point("access-control.last_event", "access-control", "Last Event")
            await asyncio.sleep(POLL_INTERVAL_S)
