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
from .state import fault_device, fault_point, set_point

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

                set_point(
                    "fire-panel.condition",
                    "fire-panel",
                    "Panel Condition",
                    data["condition"].upper(),
                )
                for zone in data["zones"]:
                    point_id = f"fire-panel.zone{zone['id']}"
                    set_point(point_id, "fire-panel", zone["name"], zone["condition"].upper())

                if data["any_alarm"]:
                    await bacnet_ahu.engage_fire_interlock()
                    interlock_value = "active"
                else:
                    await bacnet_ahu.release_fire_interlock()
                    interlock_value = "inactive"
                set_point("ahu-1.fire_interlock", "ahu-1", "Fire Interlock", interlock_value)
            except Exception:
                log.exception("Failed to poll fire panel at %s", FIRE_PANEL_URL)
                # Previously only `condition` was faulted, leaving every zone point and
                # the interlock status showing a stale value tagged status "ok" straight
                # through a fire-panel outage — exactly the condition the alarm engine's
                # fire rule keeps evaluating against. Fault everything this poller owns.
                fault_point("fire-panel.condition", "fire-panel", "Panel Condition")
                fault_device("fire-panel")
                fault_point("ahu-1.fire_interlock", "ahu-1", "Fire Interlock")
            await asyncio.sleep(POLL_INTERVAL_S)
