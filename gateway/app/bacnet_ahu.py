"""Polls (and writes to) AHU-1 over BACnet/IP.

Unlike the Modbus meter, BACnet objects are self-describing on the wire (type/name/units
all live on the object itself) — but `AHU_POINTS` below still hand-maintains a point key,
display name, and units per object instead of reading them off the device. That's a
pragmatic shortcut, not a protocol limitation: one `ReadPropertyMultiple` per poll could
fetch `objectName`/`units` directly, but for one AHU on localhost it's simpler to keep this
list in sync with sims/bacnet_devices/main.py's object list by hand (the "must match"
comments below exist for exactly that reason). See docs/bacnet-points-list.md.

One `ReadProperty` per point per poll, in sequence — twelve round trips every cycle. A
real integration would use `ReadPropertyMultiple` to batch these into one request; noted
here rather than optimized, since one AHU on localhost doesn't need it yet.
"""

from __future__ import annotations

import asyncio
import logging
import os

from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address
from bacpypes3.primitivedata import Null, ObjectIdentifier

from .state import fault_point, set_point

log = logging.getLogger("gateway.bacnet_ahu")

# Matches the static IP docker-compose.yml assigns the gateway container on bas_net.
GATEWAY_LOCAL_ADDRESS = os.environ.get("BACNET_GATEWAY_ADDRESS", "10.10.0.20/24:47808")
AHU_ADDRESS = os.environ.get("BACNET_AHU_ADDRESS", "10.10.0.11:47808")
POLL_INTERVAL_S = float(os.environ.get("BACNET_POLL_INTERVAL_S", "3"))
# bacpypes3's own apduTimeout/retries didn't save us here in practice: if AHU-1 isn't up
# yet when the gateway's first request goes out, the await can hang far longer than a
# poll cycle should ever take — found by actually cold-starting the whole stack with
# `docker compose up`, not by reading the request path. Fail fast instead.
READ_TIMEOUT_S = 5.0

AV_SAT_SETPOINT = ObjectIdentifier(("analogValue", 1))
AV_STATIC_PRESSURE_SETPOINT = ObjectIdentifier(("analogValue", 2))
AO_OA_DAMPER = ObjectIdentifier(("analogOutput", 4))
BO_FAN_COMMAND = ObjectIdentifier(("binaryOutput", 1))

# BACnet priorities 1-16, lower number wins. The schedule in sims/bacnet_devices/main.py
# writes at the default (16, lowest) by setting presentValue directly — see that file's
# docstring. The fire interlock writes here at 1 so it always wins over the schedule,
# and *relinquishes* (writes Null at the same priority) to hand control back, rather
# than writing a value — verified this is how bacpypes3 expects it (a bare Python None
# doesn't cast; it has to be primitivedata.Null(())).
INTERLOCK_PRIORITY = 1

# (point key, BACnet object, display name, units) — matches sims/bacnet_devices/main.py's
# object list exactly. Order here is display order, not wire order.
AHU_POINTS: list[tuple[str, ObjectIdentifier, str, str | None]] = [
    ("occupancy_mode", ObjectIdentifier(("multiStateValue", 1)), "Occupancy Mode", None),
    ("sat_setpoint", AV_SAT_SETPOINT, "SAT Setpoint", "degC"),
    ("sat", ObjectIdentifier(("analogInput", 1)), "Supply Air Temp", "degC"),
    ("oat", ObjectIdentifier(("analogInput", 2)), "Outside Air Temp", "degC"),
    ("rat", ObjectIdentifier(("analogInput", 3)), "Return Air Temp", "degC"),
    ("heating_valve", ObjectIdentifier(("analogOutput", 3)), "Heating Valve", "%"),
    ("cooling_valve", ObjectIdentifier(("analogOutput", 2)), "Cooling Valve", "%"),
    ("oa_damper", AO_OA_DAMPER, "OA Damper", "%"),
    ("static_pressure_setpoint", AV_STATIC_PRESSURE_SETPOINT, "Static Pressure Setpoint", "inWC"),
    ("static_pressure", ObjectIdentifier(("analogInput", 4)), "Duct Static Pressure", "inWC"),
    ("fan_speed", ObjectIdentifier(("analogOutput", 1)), "Supply Fan Speed", "%"),
    ("fan_command", BO_FAN_COMMAND, "Supply Fan Command", None),
    ("fan_status", ObjectIdentifier(("binaryInput", 1)), "Supply Fan Status", None),
]

# Must match sims/bacnet_devices/main.py's OCCUPANCY_MODES (now that file's single
# source of truth for the wire-side state text and index mapping). This dict is the one
# remaining hand-synced copy — reading `stateText` live off the multi-state object would
# remove it entirely, but costs an extra ReadProperty per poll; not worth it for one AHU.
OCCUPANCY_LABELS = {1: "Occupied", 2: "Unoccupied", 3: "Warm-up"}

# A remote ReadProperty on a binary object comes back as a plain 0/1 int, not the nicer
# BinaryPV enum a local object access gives you — found by actually looking at what the
# console rendered, not by assuming the wire value matches the Python-side object API.
BINARY_POINT_KEYS = {"fan_command", "fan_status"}
BINARY_LABELS = {0: "inactive", 1: "active"}

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
    await asyncio.wait_for(
        _client_app().write_property(AHU_ADDRESS, AV_SAT_SETPOINT, "presentValue", value),
        timeout=READ_TIMEOUT_S,
    )


async def write_static_pressure_setpoint(value: float) -> None:
    await asyncio.wait_for(
        _client_app().write_property(
            AHU_ADDRESS, AV_STATIC_PRESSURE_SETPOINT, "presentValue", value
        ),
        timeout=READ_TIMEOUT_S,
    )


async def engage_fire_interlock() -> None:
    """Fan OFF, OA damper closed, at a priority the normal schedule can't override."""
    app = _client_app()
    await asyncio.wait_for(
        app.write_property(
            AHU_ADDRESS, BO_FAN_COMMAND, "presentValue", False, priority=INTERLOCK_PRIORITY
        ),
        timeout=READ_TIMEOUT_S,
    )
    await asyncio.wait_for(
        app.write_property(
            AHU_ADDRESS, AO_OA_DAMPER, "presentValue", 0.0, priority=INTERLOCK_PRIORITY
        ),
        timeout=READ_TIMEOUT_S,
    )


async def release_fire_interlock() -> None:
    """Relinquish the interlock's priority-1 commands — control returns to whatever
    the schedule (priority 16) is writing, automatically, via BACnet's own priority
    array; nothing here needs to know what that value should be."""
    app = _client_app()
    await asyncio.wait_for(
        app.write_property(
            AHU_ADDRESS, BO_FAN_COMMAND, "presentValue", Null(()), priority=INTERLOCK_PRIORITY
        ),
        timeout=READ_TIMEOUT_S,
    )
    await asyncio.wait_for(
        app.write_property(
            AHU_ADDRESS, AO_OA_DAMPER, "presentValue", Null(()), priority=INTERLOCK_PRIORITY
        ),
        timeout=READ_TIMEOUT_S,
    )


def _format_value(key: str, raw) -> float | str:
    if key == "occupancy_mode":
        return OCCUPANCY_LABELS.get(int(raw), str(raw))
    if key in BINARY_POINT_KEYS:
        return BINARY_LABELS.get(int(raw), str(raw))
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    return str(raw)


async def poll_ahu_forever() -> None:
    app = _client_app()
    while True:
        try:
            for key, object_id, name, units in AHU_POINTS:
                raw = await asyncio.wait_for(
                    app.read_property(AHU_ADDRESS, object_id, "presentValue"),
                    timeout=READ_TIMEOUT_S,
                )
                point_id = f"ahu-1.{key}"
                set_point(point_id, "ahu-1", name, _format_value(key, raw), units)
        except Exception:
            log.exception("Failed to poll AHU-1 at %s", AHU_ADDRESS)
            for key, _object_id, name, units in AHU_POINTS:
                fault_point(f"ahu-1.{key}", "ahu-1", name, units)
        await asyncio.sleep(POLL_INTERVAL_S)
