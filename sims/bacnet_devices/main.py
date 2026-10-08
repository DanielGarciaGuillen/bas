"""AHU-1, a single BACnet/IP device running a real sequence of operation.

M3: the crude "drift toward setpoint" lag from M2 is replaced by an actual control
sequence (occupancy schedule, economizer, a PI loop driving the heating/cooling valves,
a second PI loop driving supply fan speed off duct static pressure) — see
docs/sequences-of-operation.md for the plain-English version and control.py for the
tested, pure math underneath this file's BACnet wiring.

Still one device, still deferring VAV-101..104 and the rest of AHU-1's points (Filter
Alarm, Occupancy Mode override) — see docs/bacnet-points-list.md.
"""

from __future__ import annotations

import asyncio
import logging
import os

from bacpypes3.basetypes import BinaryPV
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject, AnalogValueObjectCmd
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.pdu import IPv4Address
from control import Ahu1Plant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bacnet_devices")

# Matches the static IP docker-compose.yml assigns this container on bas_net.
LOCAL_ADDRESS = os.environ.get("BACNET_LOCAL_ADDRESS", "10.10.0.11/24:47808")
UPDATE_INTERVAL_S = float(os.environ.get("AHU_UPDATE_INTERVAL_S", "2"))

# The occupancy schedule and outside air temp run on a fast "sim day" so a demo doesn't
# have to wait for real 8am/6pm — the control loops themselves (PI, actuator slew,
# thermal lag) deliberately do NOT get this acceleration, so they behave exactly like
# the already-tested, real-time math in control.py. A clock-only time-lapse, not a
# physics one. See docs/sequences-of-operation.md.
TIME_ACCEL_X = float(os.environ.get("AHU_TIME_ACCEL_X", "180"))
SIM_START_HOUR = float(os.environ.get("AHU_SIM_START_HOUR", "7.5"))

AHU1_DEVICE_INSTANCE = 10001

# BACnet multi-state objects are 1-indexed. One ordered list is the single source of
# truth for both the wire-visible stateText and the mode-name-to-index mapping, so
# reordering a mode can't silently desync the two the way two independently-maintained
# collections could. gateway/app/bacnet_ahu.py's OCCUPANCY_LABELS is a hand-synced copy
# of this list's labels — see its own comment.
OCCUPANCY_MODES: list[tuple[str, str]] = [
    ("occupied", "Occupied"),
    ("unoccupied", "Unoccupied"),
    ("warmup", "Warm-up"),
]
OCCUPANCY_STATE_TEXT = [label for _key, label in OCCUPANCY_MODES]
MODE_TO_STATE_INDEX = {key: index for index, (key, _label) in enumerate(OCCUPANCY_MODES, start=1)}


def build_device() -> tuple[NormalApplication, dict]:
    device = DeviceObject(
        objectIdentifier=("device", AHU1_DEVICE_INSTANCE), objectName="AHU-1", vendorIdentifier=999
    )
    app = NormalApplication(device, IPv4Address(LOCAL_ADDRESS))

    def add(obj):
        app.add_object(obj)
        return obj

    objects = {
        "sat_setpoint": add(
            AnalogValueObjectCmd(
                objectIdentifier=("analogValue", 1),
                objectName="AHU1-SAT-SP",
                presentValue=13.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units="degreesCelsius",
            )
        ),
        "sat": add(
            AnalogInputObject(
                objectIdentifier=("analogInput", 1),
                objectName="AHU1-SAT",
                presentValue=14.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units="degreesCelsius",
            )
        ),
        "fan_status": add(
            BinaryInputObject(
                objectIdentifier=("binaryInput", 1),
                objectName="AHU1-FAN-STATUS",
                presentValue=BinaryPV.inactive,
                statusFlags=[0, 0, 0, 0],
            )
        ),
        "oat": add(
            AnalogInputObject(
                objectIdentifier=("analogInput", 2),
                objectName="AHU1-OAT",
                presentValue=8.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units="degreesCelsius",
            )
        ),
        "rat": add(
            AnalogInputObject(
                objectIdentifier=("analogInput", 3),
                objectName="AHU1-RAT",
                presentValue=22.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units="degreesCelsius",
            )
        ),
        "static_pressure": add(
            AnalogInputObject(
                objectIdentifier=("analogInput", 4),
                objectName="AHU1-STATIC-PRESSURE",
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.01,
                units="inchesOfWater",
            )
        ),
        "static_pressure_setpoint": add(
            AnalogValueObjectCmd(
                objectIdentifier=("analogValue", 2),
                objectName="AHU1-STATIC-PRESSURE-SP",
                presentValue=1.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.01,
                units="inchesOfWater",
            )
        ),
        "fan_speed": add(
            AnalogOutputObject(
                objectIdentifier=("analogOutput", 1),
                objectName="AHU1-FAN-SPEED",
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.5,
                units="percent",
            )
        ),
        "cooling_valve": add(
            AnalogOutputObject(
                objectIdentifier=("analogOutput", 2),
                objectName="AHU1-COOLING-VALVE",
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.5,
                units="percent",
            )
        ),
        "heating_valve": add(
            AnalogOutputObject(
                objectIdentifier=("analogOutput", 3),
                objectName="AHU1-HEATING-VALVE",
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.5,
                units="percent",
            )
        ),
        "oa_damper": add(
            AnalogOutputObject(
                objectIdentifier=("analogOutput", 4),
                objectName="AHU1-OA-DAMPER",
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.5,
                units="percent",
            )
        ),
        "fan_command": add(
            BinaryOutputObject(
                objectIdentifier=("binaryOutput", 1),
                objectName="AHU1-FAN-COMMAND",
                presentValue=BinaryPV.inactive,
                statusFlags=[0, 0, 0, 0],
            )
        ),
        "occupancy_mode": add(
            MultiStateValueObject(
                objectIdentifier=("multiStateValue", 1),
                objectName="AHU1-OCC-MODE",
                presentValue=MODE_TO_STATE_INDEX["unoccupied"],
                statusFlags=[0, 0, 0, 0],
                numberOfStates=len(OCCUPANCY_STATE_TEXT),
                stateText=OCCUPANCY_STATE_TEXT,
            )
        ),
    }
    return app, objects


async def update_ahu1(objects: dict) -> None:
    plant = Ahu1Plant(time_accel_x=TIME_ACCEL_X, sim_start_hour=SIM_START_HOUR)
    while True:
        await asyncio.sleep(UPDATE_INTERVAL_S)

        sat_setpoint = float(objects["sat_setpoint"].presentValue)
        pressure_setpoint = float(objects["static_pressure_setpoint"].presentValue)
        result = plant.step(UPDATE_INTERVAL_S, sat_setpoint, pressure_setpoint)

        objects["sat"].presentValue = round(plant.sat_c, 2)
        objects["oat"].presentValue = round(result["oat_c"], 2)
        objects["rat"].presentValue = round(plant.rat_c, 2)
        objects["static_pressure"].presentValue = round(plant.pressure_inwc, 3)
        objects["fan_speed"].presentValue = round(plant.fan_speed_pct, 1)
        objects["cooling_valve"].presentValue = round(result["cooling_pct"], 1)
        objects["heating_valve"].presentValue = round(result["heating_pct"], 1)
        objects["oa_damper"].presentValue = round(plant.oa_damper_pct, 1)
        objects["fan_command"].presentValue = (
            BinaryPV.active if result["fan_running"] else BinaryPV.inactive
        )
        objects["fan_status"].presentValue = objects["fan_command"].presentValue
        objects["occupancy_mode"].presentValue = MODE_TO_STATE_INDEX[result["mode"]]

        log.debug(
            "mode=%s SAT=%.2f(sp=%.1f) OAT=%.2f RAT=%.2f OA%%=%.0f fan=%.0f%% P=%.3f",
            result["mode"],
            plant.sat_c,
            sat_setpoint,
            result["oat_c"],
            plant.rat_c,
            plant.oa_damper_pct,
            plant.fan_speed_pct,
            plant.pressure_inwc,
        )


async def main() -> None:
    app, objects = build_device()
    log.info(
        "AHU-1 (device %s) listening on %s, sim day starting at hour %.1f (%.0fx real time)",
        AHU1_DEVICE_INSTANCE,
        LOCAL_ADDRESS,
        SIM_START_HOUR,
        TIME_ACCEL_X,
    )
    try:
        await update_ahu1(objects)
    finally:
        app.close()


if __name__ == "__main__":
    asyncio.run(main())
