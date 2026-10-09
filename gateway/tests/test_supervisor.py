import pytest
from app import bacnet_ahu, supervisor
from app.points import Point

NORMAL_CONDITION = Point(
    id="fire-panel.condition", device="fire-panel", name="Panel Condition", value="NORMAL"
)
ALARM_CONDITION = Point(
    id="fire-panel.condition", device="fire-panel", name="Panel Condition", value="ALARM"
)
TROUBLE_CONDITION = Point(
    id="fire-panel.condition", device="fire-panel", name="Panel Condition", value="TROUBLE"
)
FAULTED_CONDITION = Point(
    id="fire-panel.condition",
    device="fire-panel",
    name="Panel Condition",
    value=None,
    status="fault",
)


# --- decide_interlock(): pure, no BACnet involved ------------------------------------


def test_decide_interlock_engages_on_alarm():
    assert supervisor.decide_interlock({"fire-panel.condition": ALARM_CONDITION}) is True


def test_decide_interlock_releases_on_normal():
    assert supervisor.decide_interlock({"fire-panel.condition": NORMAL_CONDITION}) is False


def test_decide_interlock_releases_on_trouble_or_supervisory_too():
    # Only ALARM engages the interlock — a TROUBLE or SUPERVISORY condition (no zone
    # actually in alarm) must not force the fan off.
    assert supervisor.decide_interlock({"fire-panel.condition": TROUBLE_CONDITION}) is False


def test_decide_interlock_is_unknown_when_the_point_is_faulted():
    assert supervisor.decide_interlock({"fire-panel.condition": FAULTED_CONDITION}) is None


def test_decide_interlock_is_unknown_when_the_point_has_never_been_published():
    assert supervisor.decide_interlock({}) is None


# --- apply_interlock(): the thin executor, with bacnet_ahu's real functions faked out


class _Recorder:
    def __init__(self):
        self.calls: list[str] = []

    async def engage(self):
        self.calls.append("engage")

    async def release(self):
        self.calls.append("release")


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(bacnet_ahu, "engage_fire_interlock", rec.engage)
    monkeypatch.setattr(bacnet_ahu, "release_fire_interlock", rec.release)
    return rec


@pytest.mark.asyncio
async def test_apply_interlock_true_calls_engage(recorder):
    await supervisor.apply_interlock(True)
    assert recorder.calls == ["engage"]


@pytest.mark.asyncio
async def test_apply_interlock_false_calls_release(recorder):
    await supervisor.apply_interlock(False)
    assert recorder.calls == ["release"]


@pytest.mark.asyncio
async def test_apply_interlock_is_idempotent_and_re_sends_every_call(recorder):
    # Self-healing across a gateway restart depends on this: deciding "engage" twice in
    # a row must call engage_fire_interlock() twice, not skip the second call because
    # nothing changed.
    await supervisor.apply_interlock(True)
    await supervisor.apply_interlock(True)
    assert recorder.calls == ["engage", "engage"]
