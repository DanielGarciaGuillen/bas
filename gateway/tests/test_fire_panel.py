import pytest
from app import fire_panel
from app.points import Point

PANEL_NORMAL = {
    "condition": "normal",
    "any_alarm": False,
    "zones": [
        {"id": 1, "name": "Smoke Detector — Lobby", "condition": "normal"},
        {"id": 2, "name": "Smoke Detector — Office Area", "condition": "normal"},
    ],
}

PANEL_ALARM = {
    "condition": "alarm",
    "any_alarm": True,
    "zones": [
        {"id": 1, "name": "Smoke Detector — Lobby", "condition": "alarm"},
        {"id": 2, "name": "Smoke Detector — Office Area", "condition": "normal"},
    ],
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, payload=None, raise_on_get=False):
        self._payload = payload
        self._raise_on_get = raise_on_get

    async def get(self, path, params=None):
        if self._raise_on_get:
            raise OSError("connection refused")
        return _FakeResponse(self._payload)


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    fire_panel._client = None
    # Both interlock writes are real BACnet calls in production; stub them for the
    # poller test so it only exercises the fire-panel transport, not bacnet_ahu's.
    monkeypatch.setattr(fire_panel.bacnet_ahu, "engage_fire_interlock", _noop)
    monkeypatch.setattr(fire_panel.bacnet_ahu, "release_fire_interlock", _noop)
    yield
    fire_panel._client = None


async def _noop():
    pass


@pytest.mark.asyncio
async def test_read_returns_condition_zones_and_interlock_on_success():
    fire_panel._client = _FakeHttpClient(payload=PANEL_NORMAL)
    points = await fire_panel.read({})
    by_id = {p.id: p for p in points}
    assert by_id["fire-panel.condition"].value == "NORMAL"
    assert by_id["fire-panel.zone1"].value == "NORMAL"
    assert by_id["ahu-1.fire_interlock"].value == "inactive"
    assert all(p.status == "ok" for p in points)


@pytest.mark.asyncio
async def test_read_reports_interlock_active_during_an_alarm():
    fire_panel._client = _FakeHttpClient(payload=PANEL_ALARM)
    points = await fire_panel.read({})
    by_id = {p.id: p for p in points}
    assert by_id["fire-panel.condition"].value == "ALARM"
    assert by_id["fire-panel.zone1"].value == "ALARM"
    assert by_id["ahu-1.fire_interlock"].value == "active"


@pytest.mark.asyncio
async def test_read_faults_condition_interlock_and_every_known_zone_on_failure():
    fire_panel._client = _FakeHttpClient(raise_on_get=True)
    known = {
        "fire-panel.zone1": Point(
            id="fire-panel.zone1", device="fire-panel", name="Lobby", value="NORMAL"
        ),
        "fire-panel.zone2": Point(
            id="fire-panel.zone2", device="fire-panel", name="Office", value="NORMAL"
        ),
        "access-control.door1": Point(
            id="access-control.door1", device="access-control", name="Main", value="NORMAL"
        ),
    }
    points = await fire_panel.read(known)
    by_id = {p.id: p for p in points}

    assert by_id["fire-panel.condition"].status == "fault"
    assert by_id["fire-panel.zone1"].status == "fault"
    assert by_id["fire-panel.zone1"].name == "Lobby"  # name preserved from `known`
    assert by_id["fire-panel.zone2"].status == "fault"
    assert by_id["ahu-1.fire_interlock"].status == "fault"
    # A different device's point is untouched — it isn't even in the returned list.
    assert "access-control.door1" not in by_id


@pytest.mark.asyncio
async def test_read_faults_condition_and_interlock_even_on_the_very_first_poll():
    # No prior points known at all — `fire-panel.condition` and the interlock must still
    # be visible as faulted, not silently absent.
    fire_panel._client = _FakeHttpClient(raise_on_get=True)
    points = await fire_panel.read({})
    by_id = {p.id: p for p in points}
    assert by_id["fire-panel.condition"].status == "fault"
    assert by_id["ahu-1.fire_interlock"].status == "fault"
