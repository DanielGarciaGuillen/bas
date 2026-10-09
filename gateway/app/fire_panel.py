"""Polls the fire alarm panel sim (REST, not a field protocol — see
docs/fire-alarm-notes.md) and drives the AHU-1 fire interlock from it.

The interlock write is idempotent and re-sent every poll cycle rather than edge-triggered
on a state transition: simpler, and self-healing if the gateway itself restarts mid-alarm
(no "did I already send this?" state to lose). The cost is a redundant BACnet write every
cycle while nothing has changed — acceptable for one AHU on localhost.

The interlock trigger itself stays here rather than moving to supervisor.py's own
read-a-snapshot-act-on-it job — that move is scoped to a separate issue (#16) and
depends on this poller-shell unification landing first. `read()` here does more than
read (it also writes to AHU-1), which is a known, named scope boundary, not an oversight.
"""

from __future__ import annotations

import logging
import os

import httpx

from . import bacnet_ahu
from .points import Point, PointStore

log = logging.getLogger("gateway.fire_panel")

FIRE_PANEL_URL = os.environ.get("FIRE_PANEL_URL", "http://fire-panel:8001")
POLL_INTERVAL_S = float(os.environ.get("FIRE_PANEL_POLL_INTERVAL_S", "2"))
REQUEST_TIMEOUT_S = 5.0

_client: httpx.AsyncClient | None = None


def _client_handle() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=FIRE_PANEL_URL, timeout=REQUEST_TIMEOUT_S)
    return _client


async def read(known: PointStore) -> list[Point]:
    client = _client_handle()
    try:
        resp = await client.get("/panel")
        resp.raise_for_status()
        data = resp.json()

        results = [
            Point(
                id="fire-panel.condition",
                device="fire-panel",
                name="Panel Condition",
                value=data["condition"].upper(),
            )
        ]
        for zone in data["zones"]:
            results.append(
                Point(
                    id=f"fire-panel.zone{zone['id']}",
                    device="fire-panel",
                    name=zone["name"],
                    value=zone["condition"].upper(),
                )
            )

        if data["any_alarm"]:
            await bacnet_ahu.engage_fire_interlock()
            interlock_value = "active"
        else:
            await bacnet_ahu.release_fire_interlock()
            interlock_value = "inactive"
        results.append(
            Point(
                id="ahu-1.fire_interlock",
                device="ahu-1",
                name="Fire Interlock",
                value=interlock_value,
            )
        )
        return results
    except Exception:
        log.exception("Failed to poll fire panel at %s", FIRE_PANEL_URL)
        # Previously only `condition` was faulted, leaving every zone point and the
        # interlock status showing a stale value tagged status "ok" straight through a
        # fire-panel outage — exactly the condition the alarm engine's fire rule keeps
        # evaluating against. Fault `condition` and the interlock unconditionally (they
        # must be visible from the very first failed poll, before anything's ever been
        # published) plus every zone this poller has already published so far — scanned
        # from `known` rather than a fixed zone count, so a 5th zone added to the sim is
        # covered here too.
        faults = [
            Point(
                id="fire-panel.condition",
                device="fire-panel",
                name="Panel Condition",
                value=None,
                status="fault",
            )
        ]
        faults += [
            Point(
                id=point_id, device=p.device, name=p.name, value=None, units=p.units, status="fault"
            )
            for point_id, p in known.items()
            if p.device == "fire-panel" and point_id != "fire-panel.condition"
        ]
        faults.append(
            Point(
                id="ahu-1.fire_interlock",
                device="ahu-1",
                name="Fire Interlock",
                value=None,
                status="fault",
            )
        )
        return faults
