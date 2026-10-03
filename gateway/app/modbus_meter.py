"""Polls the simulated energy meter over Modbus TCP.

M1 minimum: one register, kW. See docs/modbus-register-map.md.
"""
from __future__ import annotations

import asyncio
import logging
import os

from pymodbus.client import AsyncModbusTcpClient

from .state import points

log = logging.getLogger("gateway.modbus_meter")

METER_HOST = os.environ.get("MODBUS_METER_HOST", "modbus-meter")
METER_PORT = int(os.environ.get("MODBUS_METER_PORT", "502"))
POLL_INTERVAL_S = float(os.environ.get("MODBUS_POLL_INTERVAL_S", "3"))
IR_KW = 0


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
            points["meter-1.kw"] = {
                "id": "meter-1.kw",
                "device": "meter-1",
                "name": "kW Total",
                "value": decode_kw(result.registers[0]),
                "units": "kW",
                "status": "ok",
            }
        except Exception:
            log.exception("Failed to poll Modbus meter at %s:%s", METER_HOST, METER_PORT)
            points["meter-1.kw"] = {
                "id": "meter-1.kw",
                "device": "meter-1",
                "name": "kW Total",
                "value": None,
                "units": "kW",
                "status": "fault",
            }
        await asyncio.sleep(POLL_INTERVAL_S)
