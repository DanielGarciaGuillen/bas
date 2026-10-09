import pytest
from app import access_control
from app.points import Point

STATE_NORMAL = {
    "doors": [
        {"id": 1, "name": "Main Entrance", "state": "normal"},
        {"id": 2, "name": "Server Room", "state": "normal"},
        {"id": 3, "name": "Mechanical Room", "state": "normal"},
    ]
}

EVENTS_ONE = [{"reason": "Alice Chen granted at Main Entrance"}]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, state=None, events=None, raise_on_get=False):
        self._state = state
        self._events = events if events is not None else []
        self._raise_on_get = raise_on_get

    async def get(self, path, params=None):
        if self._raise_on_get:
            raise OSError("connection refused")
        if path == "/state":
            return _FakeResponse(self._state)
        return _FakeResponse(self._events)


@pytest.fixture(autouse=True)
def _reset_client():
    access_control._client = None
    yield
    access_control._client = None


@pytest.mark.asyncio
async def test_read_returns_every_door_and_the_last_event_on_success():
    access_control._client = _FakeHttpClient(state=STATE_NORMAL, events=EVENTS_ONE)
    points = await access_control.read({})
    by_id = {p.id: p for p in points}
    assert by_id["access-control.door1"].value == "NORMAL"
    assert by_id["access-control.door1"].name == "Main Entrance"
    assert by_id["access-control.door3"].value == "NORMAL"
    assert by_id["access-control.last_event"].value == "Alice Chen granted at Main Entrance"
    assert all(p.status == "ok" for p in points)


@pytest.mark.asyncio
async def test_read_defaults_last_event_to_an_em_dash_when_there_are_none_yet():
    access_control._client = _FakeHttpClient(state=STATE_NORMAL, events=[])
    points = await access_control.read({})
    by_id = {p.id: p for p in points}
    assert by_id["access-control.last_event"].value == "—"


@pytest.mark.asyncio
async def test_read_faults_last_event_and_every_known_door_on_failure():
    access_control._client = _FakeHttpClient(raise_on_get=True)
    known = {
        "access-control.door1": Point(
            id="access-control.door1", device="access-control", name="Main Entrance", value="NORMAL"
        ),
        "access-control.door2": Point(
            id="access-control.door2", device="access-control", name="Server Room", value="FORCED"
        ),
        "fire-panel.condition": Point(
            id="fire-panel.condition", device="fire-panel", name="Panel Condition", value="NORMAL"
        ),
    }
    points = await access_control.read(known)
    by_id = {p.id: p for p in points}

    assert by_id["access-control.door1"].status == "fault"
    assert by_id["access-control.door1"].name == "Main Entrance"  # name preserved
    assert by_id["access-control.door2"].status == "fault"
    assert by_id["access-control.last_event"].status == "fault"
    # A different device's point is untouched — not even in the returned list.
    assert "fire-panel.condition" not in by_id


@pytest.mark.asyncio
async def test_read_faults_last_event_even_on_the_very_first_poll():
    access_control._client = _FakeHttpClient(raise_on_get=True)
    points = await access_control.read({})
    by_id = {p.id: p for p in points}
    assert by_id["access-control.last_event"].status == "fault"
    # No doors were ever known, so none are fabricated — just the always-faulted point.
    assert len(points) == 1


@pytest.mark.asyncio
async def test_read_covers_a_door_beyond_the_default_three():
    # Regression companion to the alarm engine's own #4 fix: the poller itself must not
    # assume a fixed door count either.
    state_with_four_doors = {
        "doors": [*STATE_NORMAL["doors"], {"id": 4, "name": "Loading Dock", "state": "normal"}]
    }
    access_control._client = _FakeHttpClient(state=state_with_four_doors, events=[])
    points = await access_control.read({})
    assert any(p.id == "access-control.door4" for p in points)
