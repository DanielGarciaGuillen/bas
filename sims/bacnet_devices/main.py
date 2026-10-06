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
import random

from bacpypes3.basetypes import BinaryPV
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject, AnalogValueObjectCmd
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.pdu import IPv4Address
from control import (
    ACTUATOR_SLEW_PCT_PER_TICK,
    COIL_MAX_DELTA_C,
    FAN_PID_KI,
    FAN_PID_KP,
    OA_DAMPER_MIN_PCT,
    SAT_PID_KI,
    SAT_PID_KP,
    SAT_RESPONSE_RATE,
    PIController,
    economizer_oa_damper_pct,
    fan_curve_pressure_inwc,
    mixed_air_temp_c,
    outside_air_temp_c,
    ramp_toward,
    schedule_mode,
    split_range_valves,
    step_return_air_temp_c,
)

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

# BACnet multi-state objects are 1-indexed; order must match stateText below.
OCCUPANCY_STATE_TEXT = ["Occupied", "Unoccupied", "Warm-up"]
MODE_TO_STATE_INDEX = {"occupied": 1, "unoccupied": 2, "warmup": 3}


class Ahu1Plant:
    """Everything the sequence of operation needs to remember between ticks.

    All the actual decisions are the pure functions in control.py — this class only
    holds state across ticks and is the thing main() advances once per update.
    """

    def __init__(self) -> None:
        self.sim_seconds = SIM_START_HOUR * 3600.0
        self.sat_c = 14.0
        self.rat_c = 22.0
        self.oa_damper_pct = OA_DAMPER_MIN_PCT
        self.fan_speed_pct = 0.0
        self.pressure_inwc = 0.0
        self.fan_curve_disturbance = 1.0
        self.sat_pid = PIController(
            kp=SAT_PID_KP, ki=SAT_PID_KI, output_min=-100.0, output_max=100.0
        )
        self.fan_pid = PIController(kp=FAN_PID_KP, ki=FAN_PID_KI, output_min=0.0, output_max=100.0)

    def step(self, dt_s: float, sat_setpoint_c: float, pressure_setpoint_inwc: float) -> dict:
        self.sim_seconds += dt_s * TIME_ACCEL_X
        hour_of_day = (self.sim_seconds / 3600.0) % 24.0
        mode = schedule_mode(hour_of_day)
        fan_running = mode in ("occupied", "warmup")
        oat_c = outside_air_temp_c(hour_of_day)

        self.fan_curve_disturbance = max(
            0.85, min(1.15, self.fan_curve_disturbance + random.uniform(-0.01, 0.01))
        )
        self.rat_c = step_return_air_temp_c(
            self.rat_c, self.sat_c, occupied=(mode == "occupied"), dt_s=dt_s
        )

        if fan_running:
            sat_error = sat_setpoint_c - self.sat_c
            net = self.sat_pid.step(sat_error, dt_s)
            heating_pct, cooling_pct = split_range_valves(net)
            oa_target = economizer_oa_damper_pct(oat_c, self.rat_c, fan_running, cooling_pct)
        else:
            self.sat_pid.reset()
            heating_pct, cooling_pct, oa_target = 0.0, 0.0, 0.0

        self.oa_damper_pct = ramp_toward(self.oa_damper_pct, oa_target, ACTUATOR_SLEW_PCT_PER_TICK)
        mixed_c = mixed_air_temp_c(oat_c, self.rat_c, self.oa_damper_pct)
        coil_effect_c = (
            heating_pct / 100.0 * COIL_MAX_DELTA_C - cooling_pct / 100.0 * COIL_MAX_DELTA_C
        )
        sat_target_c = mixed_c + coil_effect_c if fan_running else self.rat_c
        self.sat_c += (sat_target_c - self.sat_c) * SAT_RESPONSE_RATE

        if fan_running:
            pressure_error = pressure_setpoint_inwc - self.pressure_inwc
            fan_target_pct = self.fan_pid.step(pressure_error, dt_s)
        else:
            self.fan_pid.reset()
            fan_target_pct = 0.0
        self.fan_speed_pct = ramp_toward(
            self.fan_speed_pct, fan_target_pct, ACTUATOR_SLEW_PCT_PER_TICK
        )
        self.pressure_inwc = fan_curve_pressure_inwc(self.fan_speed_pct, self.fan_curve_disturbance)

        return {
            "mode": mode,
            "fan_running": fan_running,
            "oat_c": oat_c,
            "heating_pct": heating_pct,
            "cooling_pct": cooling_pct,
        }


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
    plant = Ahu1Plant()
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
