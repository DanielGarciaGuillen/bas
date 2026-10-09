"""One poll-loop shell every device module's `read()` plugs into.

Before this existed, `modbus_meter.py`, `bacnet_ahu.py`, `fire_panel.py`, and
`access_control.py` each hand-wrote an identical `while True` / `try` / `except` /
`asyncio.sleep` shape, differing only in transport and point mapping — and that
identical shape had already drifted once (the M6/#12 fault-path divergence) specifically
because there was no single place it lived to drift *from*.

The contract: `read(known)` is expected to catch its own transport errors internally and
return fault `Point`s rather than raise — `known` is the point store as of the start of
this tick, so a device module whose fault set is dynamic (fire panel's zones, access
control's doors — both sim-reported, not a fixed count) can fault whatever it has
already published without the shell needing to know the device's own point layout.
That's what makes the loop shape itself have nothing device-specific left in it; the
`try`/`except` here is a last-resort safety net for a bug in `read()` itself, not the
normal "device unreachable" path.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .points import Point, PointStore, publish

ReadFn = Callable[[PointStore], Awaitable[list[Point]]]


async def run_poller(
    name: str, interval_s: float, read: ReadFn, store: PointStore, log: logging.Logger
) -> None:
    while True:
        try:
            for point in await read(dict(store)):
                publish(store, point)
        except Exception:
            log.exception("Unexpected error polling %s (read() should have caught this)", name)
        await asyncio.sleep(interval_s)
