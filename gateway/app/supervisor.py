"""Ties the point store to the alarm engine and trend history — the piece that turns the
gateway from a polling pipe into something that actually supervises. Runs independently
of (and slower than) the individual device pollers: it only ever reads the shared
`points` snapshot they maintain, never talks to a device directly.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from . import db
from .state import alarm_engine, points

SUPERVISOR_INTERVAL_S = float(os.environ.get("SUPERVISOR_INTERVAL_S", "3"))


async def run_supervisor_forever() -> None:
    while True:
        await asyncio.sleep(SUPERVISOR_INTERVAL_S)
        now = datetime.now()

        snapshot = dict(points)
        alarm_engine.evaluate(snapshot, now)

        samples = [
            (point_id, float(p["value"]), now)
            for point_id, p in snapshot.items()
            if isinstance(p.get("value"), (int, float))
        ]
        await db.record_samples(samples)
