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

from .state import points

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
                    points[point_id] = {
                        "id": point_id,
                        "device": "access-control",
                        "name": door["name"],
                        "value": door["state"].upper(),
                        "units": None,
                        "status": "ok",
                    }

                last_event_value = latest_events[0]["reason"] if latest_events else "—"
                points["access-control.last_event"] = {
                    "id": "access-control.last_event",
                    "device": "access-control",
                    "name": "Last Event",
                    "value": last_event_value,
                    "units": None,
                    "status": "ok",
                }
            except Exception:
                log.exception("Failed to poll access control at %s", ACCESS_CONTROL_URL)
                points["access-control.last_event"] = {
                    "id": "access-control.last_event",
                    "device": "access-control",
                    "name": "Last Event",
                    "value": None,
                    "units": None,
                    "status": "fault",
                }
            await asyncio.sleep(POLL_INTERVAL_S)
