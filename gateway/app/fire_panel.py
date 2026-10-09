"""Polls the fire alarm panel sim (REST, not a field protocol — see
docs/fire-alarm-notes.md) and normalizes its zones into points.

The AHU-1 fire interlock used to be decided and driven from here too; that moved to
supervisor.py (#16) — supervisor.py's own docstring describes exactly this job ("read a
snapshot, act on it"), which is what deciding whether to engage/release the interlock
is. This module now only ever normalizes what the fire panel sim reports; it has no
BACnet dependency at all.
"""

from __future__ import annotations

import logging
import os

import httpx

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
        return results
    except Exception:
        log.exception("Failed to poll fire panel at %s", FIRE_PANEL_URL)
        # `condition` is faulted unconditionally (visible from the very first failed
        # poll, before anything's ever been published); every zone this poller has
        # already published so far is scanned from `known` rather than a fixed zone
        # count, so a 5th zone added to the sim is covered here too. The interlock point
        # (ahu-1.fire_interlock) is no longer this module's concern — supervisor.py
        # faults it independently once it sees `condition` go unknown.
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
        return faults
