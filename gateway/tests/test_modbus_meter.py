import pytest
from app import modbus_meter
from app.modbus_meter import decode_kw


def test_decode_kw_applies_x10_scale_factor():
    assert decode_kw(180) == 18.0


class _FakeResult:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):  # noqa: N802 - matches pymodbus's own method name
        return self._error


class _FakeModbusClient:
    def __init__(self, result=None, raise_on_read=False):
        self.connected = True
        self._result = result
        self._raise_on_read = raise_on_read

    async def connect(self):
        self.connected = True

    async def read_input_registers(self, address, count, slave):
        if self._raise_on_read:
            raise OSError("connection refused")
        return self._result


@pytest.fixture(autouse=True)
def _reset_client():
    modbus_meter._client = None
    yield
    modbus_meter._client = None


@pytest.mark.asyncio
async def test_read_returns_an_ok_point_on_success():
    modbus_meter._client = _FakeModbusClient(result=_FakeResult(registers=[180]))
    points = await modbus_meter.read({})
    assert len(points) == 1
    assert points[0].id == "meter-1.kw"
    assert points[0].value == 18.0
    assert points[0].status == "ok"


@pytest.mark.asyncio
async def test_read_returns_a_fault_point_when_the_transport_raises():
    modbus_meter._client = _FakeModbusClient(raise_on_read=True)
    points = await modbus_meter.read({})
    assert len(points) == 1
    assert points[0].value is None
    assert points[0].status == "fault"
    assert points[0].units == "kW"  # the fault point still carries its known units


@pytest.mark.asyncio
async def test_read_returns_a_fault_point_when_the_register_read_itself_errors():
    modbus_meter._client = _FakeModbusClient(result=_FakeResult(error=True))
    points = await modbus_meter.read({})
    assert points[0].status == "fault"
