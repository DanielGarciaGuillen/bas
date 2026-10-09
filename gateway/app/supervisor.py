"""Ties the point store to the alarm engine, trend history, and the AHU-1 fire
interlock — the piece that turns the gateway from a polling pipe into something that
actually supervises. Runs independently of (and slower than) the individual device
pollers: it only ever reads the shared `points` snapshot they maintain.

The fire interlock (#16) is the one exception to "never talks to a device directly" —
deciding whether AHU-1's fan/damper should be overridden is exactly "read a snapshot,
act on it," the same job as alarm evaluation, so it lives here rather than inside the
fire-panel poller that used to own it. `decide_interlock()` is pure (snapshot in,
True/False/None out); `apply_interlock()` is the thin executor that actually writes to
BACnet — kept separate so the decision itself is unit-testable without a live stack.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from . import bacnet_ahu, db
from .points import Point, PointStore, numeric_points, publish
from .state import alarm_engine, points

SUPERVISOR_INTERVAL_S = float(os.environ.get("SUPERVISOR_INTERVAL_S", "3"))


def decide_interlock(snapshot: PointStore) -> bool | None:
    """True = engage, False = release, None = the fire panel's condition is currently
    unknown (faulted or never published) — in which case no new BACnet command should
    be sent this tick, matching the pre-#16 behavior where a fire-panel comms failure
    meant the interlock write simply didn't happen that cycle, leaving AHU-1's actual
    state exactly where it was rather than guessing.

    Checking the panel's overall `condition` (rather than needing the sim's raw
    `any_alarm` flag directly) is equivalent: sims/fire_panel/panel.py's own
    `overall_condition()` forces condition to ALARM whenever any zone is in alarm —
    alarm beats trouble beats supervisory beats normal — so "condition == ALARM" and
    "any zone is in alarm" are the same predicate.
    """
    point = snapshot.get("fire-panel.condition")
    if point is None or point.status == "fault" or point.value is None:
        return None
    return point.value == "ALARM"


async def apply_interlock(engage: bool) -> None:
    """Idempotent, re-sent every call regardless of the previous state — self-healing
    across a gateway restart, same as before the move (see bacnet_ahu.py's own
    engage_fire_interlock()/release_fire_interlock(), unchanged by this move)."""
    if engage:
        await bacnet_ahu.engage_fire_interlock()
    else:
        await bacnet_ahu.release_fire_interlock()


async def run_supervisor_forever() -> None:
    while True:
        await asyncio.sleep(SUPERVISOR_INTERVAL_S)
        now = datetime.now()

        snapshot = dict(points)
        alarm_engine.evaluate(snapshot, now)

        samples = [(p.id, float(p.value), now) for p in numeric_points(snapshot)]
        await db.record_samples(samples)

        interlock = decide_interlock(snapshot)
        if interlock is None:
            publish(
                points,
                Point(
                    id="ahu-1.fire_interlock",
                    device="ahu-1",
                    name="Fire Interlock",
                    value=None,
                    status="fault",
                ),
            )
        else:
            await apply_interlock(interlock)
            publish(
                points,
                Point(
                    id="ahu-1.fire_interlock",
                    device="ahu-1",
                    name="Fire Interlock",
                    value="active" if interlock else "inactive",
                ),
            )
