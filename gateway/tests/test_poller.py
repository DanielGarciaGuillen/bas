import asyncio
import logging

import pytest
from app.points import Point
from app.poller import run_poller

_log = logging.getLogger("test.poller")


async def _run_briefly(read_fn, store):
    task = asyncio.create_task(run_poller("test", 0.001, read_fn, store, _log))
    await asyncio.sleep(0.02)  # let it tick several times
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_run_poller_publishes_whatever_read_returns():
    store: dict = {}
    calls = 0

    async def fake_read(known):
        nonlocal calls
        calls += 1
        return [Point(id="x", device="d", name="n", value=calls)]

    await _run_briefly(fake_read, store)

    assert calls >= 1
    assert store["x"].value == calls  # the store reflects the latest successful tick


@pytest.mark.asyncio
async def test_run_poller_passes_the_current_store_snapshot_to_read():
    store = {"existing": Point(id="existing", device="d", name="n", value=1)}
    seen_known = []

    async def fake_read(known):
        seen_known.append(known)
        return []

    await _run_briefly(fake_read, store)

    assert len(seen_known) >= 1
    assert seen_known[0]["existing"].value == 1


@pytest.mark.asyncio
async def test_run_poller_survives_an_unexpected_bug_in_read_itself():
    # The try/except in run_poller is a last-resort safety net for a bug in read() —
    # every device module is expected to catch its own transport errors and return fault
    # Points instead of raising, but the loop must not die even if one doesn't.
    store: dict = {}
    calls = 0

    async def flaky_read(known):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("a bug read() should have caught internally")
        return [Point(id="x", device="d", name="n", value="recovered")]

    await _run_briefly(flaky_read, store)

    assert calls >= 2  # the loop kept ticking after the first call's exception
    assert store["x"].value == "recovered"
