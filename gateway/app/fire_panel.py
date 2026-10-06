"""Polls the fire alarm panel sim (REST, not a field protocol — see
docs/fire-alarm-notes.md) and drives the AHU-1 fire interlock from it.

The interlock write is idempotent and re-sent every poll cycle rather than edge-triggered
on a state transition: simpler, and self-healing if the gateway itself restarts mid-alarm
(no "did I already send this?" state to lose). The cost is a redundant BACnet write every
cycle while nothing has changed — acceptable for one AHU on localhost.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from . import bacnet_ahu
from .state import points

log = logging.getLogger("gateway.fire_panel")

FIRE_PANEL_URL = os.environ.get("FIRE_PANEL_URL", "http://fire-panel:8001")
POLL_INTERVAL_S = float(os.environ.get("FIRE_PANEL_POLL_INTERVAL_S", "2"))
REQUEST_TIMEOUT_S = 5.0


async def poll_fire_panel_forever() -> None:
    async with httpx.AsyncClient(base_url=FIRE_PANEL_URL, timeout=REQUEST_TIMEOUT_S) as client:
        while True:
            try:
                resp = await client.get("/panel")
                resp.raise_for_status()
                data = resp.json()

                points["fire-panel.condition"] = {
                    "id": "fire-panel.condition",
                    "device": "fire-panel",
                    "name": "Panel Condition",
                    "value": data["condition"].upper(),
                    "units": None,
                    "status": "ok",
                }
                for zone in data["zones"]:
                    point_id = f"fire-panel.zone{zone['id']}"
                    points[point_id] = {
                        "id": point_id,
                        "device": "fire-panel",
                        "name": zone["name"],
                        "value": zone["condition"].upper(),
                        "units": None,
                        "status": "ok",
                    }

                if data["any_alarm"]:
                    await bacnet_ahu.engage_fire_interlock()
                    interlock_value = "active"
                else:
                    await bacnet_ahu.release_fire_interlock()
                    interlock_value = "inactive"
                points["ahu-1.fire_interlock"] = {
                    "id": "ahu-1.fire_interlock",
                    "device": "ahu-1",
                    "name": "Fire Interlock",
                    "value": interlock_value,
                    "units": None,
                    "status": "ok",
                }
            except Exception:
                log.exception("Failed to poll fire panel at %s", FIRE_PANEL_URL)
                points["fire-panel.condition"] = {
                    "id": "fire-panel.condition",
                    "device": "fire-panel",
                    "name": "Panel Condition",
                    "value": None,
                    "units": None,
                    "status": "fault",
                }
            await asyncio.sleep(POLL_INTERVAL_S)
