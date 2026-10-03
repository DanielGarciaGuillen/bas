"""AHU-1, a single BACnet/IP device.

M2 minimum: one device, three points — enough to prove the BACnet pipeline (device
exposes self-describing objects; gateway reads AND writes them over real BACnet/IP) without
building out the full AHU + 4-VAV point list yet. See docs/bacnet-points-list.md.

Unlike Modbus (sims/modbus_meter), nothing here is "register 0 means kW" — every point
carries its own object type, name, units, and status on the wire. That's the whole point
of this module existing.
"""

from __future__ import annotations

import asyncio
import logging
import os

from bacpypes3.basetypes import BinaryPV
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.analog import AnalogInputObject, AnalogValueObjectCmd
from bacpypes3.local.binary import BinaryInputObject
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bacnet_devices")

# Matches the static IP docker-compose.yml assigns this container on bas_net.
LOCAL_ADDRESS = os.environ.get("BACNET_LOCAL_ADDRESS", "10.10.0.11/24:47808")
UPDATE_INTERVAL_S = float(os.environ.get("AHU_UPDATE_INTERVAL_S", "2"))

AHU1_DEVICE_INSTANCE = 10001


async def simulate_ahu1(sat: AnalogInputObject, setpoint: AnalogValueObjectCmd) -> None:
    """Supply air temp drifts toward whatever the setpoint is asked to be.

    A real AHU's supply air temp is the output of a control loop (cooling/heating valves
    modulating against a PID); this is a stand-in first-order lag, just enough to make the
    setpoint write in M2's demo visibly do something. The real sequence of operation lands
    in M3.
    """
    while True:
        await asyncio.sleep(UPDATE_INTERVAL_S)
        current = float(sat.presentValue)
        target = float(setpoint.presentValue)
        sat.presentValue = round(current + (target - current) * 0.3, 2)
        log.debug("SAT %.2f -> target %.2f", sat.presentValue, target)


def build_device() -> tuple[NormalApplication, AnalogInputObject, AnalogValueObjectCmd]:
    device = DeviceObject(
        objectIdentifier=("device", AHU1_DEVICE_INSTANCE),
        objectName="AHU-1",
        vendorIdentifier=999,
    )
    app = NormalApplication(device, IPv4Address(LOCAL_ADDRESS))

    setpoint = AnalogValueObjectCmd(
        objectIdentifier=("analogValue", 1),
        objectName="AHU1-SAT-SP",
        presentValue=13.0,
        statusFlags=[0, 0, 0, 0],
        covIncrement=0.1,
        units="degreesCelsius",
    )
    app.add_object(setpoint)

    sat = AnalogInputObject(
        objectIdentifier=("analogInput", 1),
        objectName="AHU1-SAT",
        presentValue=14.0,
        statusFlags=[0, 0, 0, 0],
        covIncrement=0.1,
        units="degreesCelsius",
    )
    app.add_object(sat)

    fan_status = BinaryInputObject(
        objectIdentifier=("binaryInput", 1),
        objectName="AHU1-FAN-STATUS",
        presentValue=BinaryPV.active,
        statusFlags=[0, 0, 0, 0],
    )
    app.add_object(fan_status)

    return app, sat, setpoint


async def main() -> None:
    app, sat, setpoint = build_device()
    log.info("AHU-1 (device %s) listening on %s", AHU1_DEVICE_INSTANCE, LOCAL_ADDRESS)
    try:
        await simulate_ahu1(sat, setpoint)
    finally:
        app.close()


if __name__ == "__main__":
    asyncio.run(main())
