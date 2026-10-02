"""BuildingOps Lab gateway.

M1 minimum: poll the simulated Modbus meter's kW register and serve the latest value.
One normalized point shape (id, device, name, value, units, status) will carry through to
BACnet/fire/access points in later milestones — kept simple for now since there's only one
source.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymodbus.client import AsyncModbusTcpClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gateway")

METER_HOST = os.environ.get("MODBUS_METER_HOST", "modbus-meter")
METER_PORT = int(os.environ.get("MODBUS_METER_PORT", "502"))
POLL_INTERVAL_S = float(os.environ.get("MODBUS_POLL_INTERVAL_S", "3"))
IR_KW = 0

latest_point = {
    "id": "meter-1.kw",
    "device": "meter-1",
    "name": "kW Total",
    "value": None,
    "units": "kW",
    "status": "fault",
}


def decode_kw(raw_register: int) -> float:
    """Register is kW x10 — see docs/modbus-register-map.md."""
    return raw_register / 10.0


async def poll_meter_forever() -> None:
    client = AsyncModbusTcpClient(METER_HOST, port=METER_PORT)
    while True:
        try:
            if not client.connected:
                await client.connect()
            result = await client.read_input_registers(IR_KW, count=1, slave=1)
            if result.isError():
                raise OSError(f"Modbus error reading meter: {result}")
            latest_point["value"] = decode_kw(result.registers[0])
            latest_point["status"] = "ok"
        except Exception:
            log.exception("Failed to poll Modbus meter at %s:%s", METER_HOST, METER_PORT)
            latest_point["status"] = "fault"
        await asyncio.sleep(POLL_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_meter_forever())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="BuildingOps Lab Gateway", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/points")
async def list_points() -> list[dict]:
    return [latest_point]
