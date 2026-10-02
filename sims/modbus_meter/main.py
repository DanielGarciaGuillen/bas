"""Energy meter simulator exposed over Modbus TCP.

M1 minimum: one value, kW, in one input register (FC04), address 0, scaled x10
(register / 10 = kW). Documented in docs/modbus-register-map.md. More registers
(voltage, current, kWh, ...) can be added the same way once the pipeline is proven.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("modbus_meter")

HOST = os.environ.get("MODBUS_HOST", "0.0.0.0")
PORT = int(os.environ.get("MODBUS_PORT", "502"))
UPDATE_INTERVAL_S = float(os.environ.get("METER_UPDATE_INTERVAL_S", "2"))

IR_KW = 0  # input register address, kW x10
SLAVE_ID = 1


async def update_kw(context: ModbusServerContext) -> None:
    kw = 18.0
    slave = context[SLAVE_ID]
    while True:
        await asyncio.sleep(UPDATE_INTERVAL_S)
        kw = max(2.0, min(80.0, kw + random.uniform(-1.5, 1.6)))
        slave.setValues(4, IR_KW, [round(kw * 10)])
        log.debug("kW=%.2f", kw)


def build_context() -> ModbusServerContext:
    # pymodbus's ModbusSlaveContext maps protocol address A to block index A+1, so the
    # block needs one extra slot beyond what's addressed (index 0 here is unused).
    ir_block = ModbusSequentialDataBlock(0, [0, 180])  # index 1 (addr 0) starts at 18.0 kW
    slave = ModbusSlaveContext(ir=ir_block)
    return ModbusServerContext(slaves={SLAVE_ID: slave}, single=False)


async def main() -> None:
    context = build_context()
    log.info("Starting Modbus TCP meter sim on %s:%s (unit id %s)", HOST, PORT, SLAVE_ID)
    await asyncio.gather(
        StartAsyncTcpServer(context=context, address=(HOST, PORT)),
        update_kw(context),
    )


if __name__ == "__main__":
    asyncio.run(main())
