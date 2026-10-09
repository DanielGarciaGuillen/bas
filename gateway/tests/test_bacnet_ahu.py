import pytest
from app import bacnet_ahu


class _FakeApp:
    def __init__(self, values=None, raise_on_nth_read=None):
        # values: dict mapping object_id -> raw presentValue to return.
        self._values = values or {}
        self._raise_on_nth_read = raise_on_nth_read
        self._read_count = 0

    async def read_property(self, address, object_id, property_name):
        self._read_count += 1
        if self._raise_on_nth_read is not None and self._read_count == self._raise_on_nth_read:
            raise OSError("BACnet request timed out")
        return self._values[object_id]


@pytest.fixture(autouse=True)
def _reset_app():
    bacnet_ahu._app = None
    yield
    bacnet_ahu._app = None


def _all_ok_values():
    """One plausible raw value per AHU_POINTS entry, in order."""
    return {
        bacnet_ahu.AHU_POINTS[0][1]: 1,  # occupancy_mode -> Occupied
        bacnet_ahu.AHU_POINTS[1][1]: 13.0,  # sat_setpoint
        bacnet_ahu.AHU_POINTS[2][1]: 13.2,  # sat
        bacnet_ahu.AHU_POINTS[3][1]: 7.0,  # oat
        bacnet_ahu.AHU_POINTS[4][1]: 21.9,  # rat
        bacnet_ahu.AHU_POINTS[5][1]: 10.0,  # heating_valve
        bacnet_ahu.AHU_POINTS[6][1]: 0.0,  # cooling_valve
        bacnet_ahu.AHU_POINTS[7][1]: 55.0,  # oa_damper
        bacnet_ahu.AHU_POINTS[8][1]: 1.0,  # static_pressure_setpoint
        bacnet_ahu.AHU_POINTS[9][1]: 0.1,  # static_pressure
        bacnet_ahu.AHU_POINTS[10][1]: 20.0,  # fan_speed
        bacnet_ahu.AHU_POINTS[11][1]: 1,  # fan_command -> active
        bacnet_ahu.AHU_POINTS[12][1]: 1,  # fan_status -> active
    }


@pytest.mark.asyncio
async def test_read_returns_one_ok_point_per_ahu_point_on_success():
    bacnet_ahu._app = _FakeApp(values=_all_ok_values())
    points = await bacnet_ahu.read({})
    assert len(points) == len(bacnet_ahu.AHU_POINTS)
    assert all(p.status == "ok" for p in points)
    by_id = {p.id: p for p in points}
    assert by_id["ahu-1.occupancy_mode"].value == "Occupied"
    assert by_id["ahu-1.fan_status"].value == "active"
    assert by_id["ahu-1.sat"].value == 13.2


@pytest.mark.asyncio
async def test_read_faults_every_point_if_any_single_read_fails_partway_through():
    # The 5th ReadProperty call fails; all 13 points must still come back faulted, not
    # just the ones not yet read — a partial, inconsistent snapshot is never published.
    bacnet_ahu._app = _FakeApp(values=_all_ok_values(), raise_on_nth_read=5)
    points = await bacnet_ahu.read({})
    assert len(points) == len(bacnet_ahu.AHU_POINTS)
    assert all(p.status == "fault" for p in points)
    assert all(p.value is None for p in points)
    # Units are preserved on the fault points, same as every other poller's fault path.
    by_id = {p.id: p for p in points}
    assert by_id["ahu-1.sat"].units == "degC"
