"""Polls (and writes to) AHU-1 over BACnet/IP.

Unlike the Modbus meter, nothing here needs a hand-maintained register map: every object
carries its own type/name/units, so the gateway reads those directly off the device instead
of hardcoding them. See docs/bacnet-points-list.md.
"""
from __future__ import annotations

import asyncio
import logging
import os

from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier

from .state import points

log = logging.getLogger("gateway.bacnet_ahu")

# Matches the static IP docker-compose.yml assigns the gateway container on bas_net.
GATEWAY_LOCAL_ADDRESS = os.environ.get("BACNET_GATEWAY_ADDRESS", "10.10.0.20/24:47808")
AHU_ADDRESS = os.environ.get("BACNET_AHU_ADDRESS", "10.10.0.11:47808")
POLL_INTERVAL_S = float(os.environ.get("BACNET_POLL_INTERVAL_S", "3"))

AI_SAT = ObjectIdentifier(("analogInput", 1))
AV_SAT_SETPOINT = ObjectIdentifier(("analogValue", 1))
BI_FAN_STATUS = ObjectIdentifier(("binaryInput", 1))

_app: NormalApplication | None = None


def _client_app() -> NormalApplication:
    global _app
    if _app is None:
        device = DeviceObject(
            objectIdentifier=("device", 599),
            objectName="buildingops-gateway",
            vendorIdentifier=999,
        )
        _app = NormalApplication(device, IPv4Address(GATEWAY_LOCAL_ADDRESS))
    return _app


async def write_sat_setpoint(value: float) -> None:
    await _client_app().write_property(AHU_ADDRESS, AV_SAT_SETPOINT, "presentValue", value)


async def poll_ahu_forever() -> None:
    app = _client_app()
    while True:
        try:
            sat = await app.read_property(AHU_ADDRESS, AI_SAT, "presentValue")
            setpoint = await app.read_property(AHU_ADDRESS, AV_SAT_SETPOINT, "presentValue")
            fan_status = await app.read_property(AHU_ADDRESS, BI_FAN_STATUS, "presentValue")

            points["ahu-1.sat"] = {
                "id": "ahu-1.sat", "device": "ahu-1", "name": "Supply Air Temp",
                "value": round(float(sat), 2), "units": "degC", "status": "ok",
            }
            points["ahu-1.sat_setpoint"] = {
                "id": "ahu-1.sat_setpoint", "device": "ahu-1", "name": "SAT Setpoint",
                "value": round(float(setpoint), 2), "units": "degC", "status": "ok",
            }
            points["ahu-1.fan_status"] = {
                "id": "ahu-1.fan_status", "device": "ahu-1", "name": "Supply Fan Status",
                "value": str(fan_status), "units": None, "status": "ok",
            }
        except Exception:
            log.exception("Failed to poll AHU-1 at %s", AHU_ADDRESS)
            for point_id, name, units in (
                ("ahu-1.sat", "Supply Air Temp", "degC"),
                ("ahu-1.sat_setpoint", "SAT Setpoint", "degC"),
                ("ahu-1.fan_status", "Supply Fan Status", None),
            ):
                points[point_id] = {
                    "id": point_id, "device": "ahu-1", "name": name,
                    "value": None, "units": units, "status": "fault",
                }
        await asyncio.sleep(POLL_INTERVAL_S)
