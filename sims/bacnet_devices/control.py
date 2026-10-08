"""Pure control-logic functions for AHU-1's sequence of operation.

Kept separate from main.py (which only wires these into BACnet objects and an asyncio
loop) so the actual control math is unit-testable without a running BACnet stack. See
docs/sequences-of-operation.md for the plain-English version of each sequence.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# --- Occupancy schedule -------------------------------------------------------------
WARMUP_START_HOUR = 7.0
OCCUPIED_START_HOUR = 8.0
OCCUPIED_END_HOUR = 18.0


def schedule_mode(hour_of_day: float) -> str:
    """Return "warmup" | "occupied" | "unoccupied" for a 0-24 hour clock."""
    if WARMUP_START_HOUR <= hour_of_day < OCCUPIED_START_HOUR:
        return "warmup"
    if OCCUPIED_START_HOUR <= hour_of_day < OCCUPIED_END_HOUR:
        return "occupied"
    return "unoccupied"


# --- Outside air temp model ---------------------------------------------------------
OAT_MEAN_C = 8.0
OAT_AMPLITUDE_C = 6.0
OAT_PEAK_HOUR = 15.0  # outside air temp peaks mid-afternoon


def outside_air_temp_c(hour_of_day: float) -> float:
    """A plausible Ottawa fall-day temperature curve, trough before dawn, peak ~3pm."""
    return OAT_MEAN_C + OAT_AMPLITUDE_C * math.cos(
        2 * math.pi * (hour_of_day - OAT_PEAK_HOUR) / 24.0
    )


# --- "Virtual zone" return air temp (stands in for real zones until VAVs exist) -----
def step_return_air_temp_c(rat_c: float, sat_c: float, occupied: bool, dt_s: float) -> float:
    """First-order lag toward supply air temp, with a small occupancy heat gain.

    > Real world: a real AHU serves multiple zones, each with its own load (occupancy,
    > solar gain, outside walls). Return air temp is the mixed average of all of them.
    > This project has no VAVs yet, so RAT is a single lumped proxy — documented here
    > rather than hidden, same as the Modbus/BACnet simplifications in M1/M2.
    """
    time_constant_s = 1800.0  # how fast the space responds to supply air, ~30 min
    occupancy_bias_c = 1.5 if occupied else 0.0
    target = sat_c + occupancy_bias_c
    alpha = 1 - math.exp(-dt_s / time_constant_s)
    return rat_c + (target - rat_c) * alpha


# --- Economizer ----------------------------------------------------------------------
OA_DAMPER_MIN_PCT = 20.0  # ventilation minimum whenever the fan is running
OA_DAMPER_MAX_PCT = 90.0  # never fully open; keep some return air for stability
ECONOMIZER_DEADBAND_C = 1.0
ECONOMIZER_LOW_LIMIT_C = -5.0  # below this, risk of coil freeze — don't rely on OA


def economizer_oa_damper_pct(
    oat_c: float, rat_c: float, fan_running: bool, cooling_demand_pct: float
) -> float:
    """Outside air damper position: free cooling, but only when cooling is wanted.

    Opens wide only when the loop is actually calling for cooling (there's no point
    flooding the AHU with cold outside air during a heating call just because it's
    cold outside) *and* OAT is usefully below RAT (with a deadband so it doesn't hunt)
    *and* not so cold the coils risk freezing. Otherwise sits at the ventilation
    minimum while running, or fully closed when the fan is off.
    """
    if not fan_running:
        return 0.0
    economizer_helps = ECONOMIZER_LOW_LIMIT_C < oat_c < (rat_c - ECONOMIZER_DEADBAND_C)
    if cooling_demand_pct > 0 and economizer_helps:
        return OA_DAMPER_MAX_PCT
    return OA_DAMPER_MIN_PCT


def ramp_toward(current: float, target: float, max_delta: float) -> float:
    """Move `current` toward `target` by at most `max_delta` per call.

    A real damper/valve actuator takes time to travel, it doesn't teleport. Without
    this, the economizer's on/off switching snaps the mixed-air temp between two
    extremes every tick and the SAT loop oscillates forever instead of settling —
    found by actually running the loop for hundreds of ticks, not by inspecting the
    functions individually.
    """
    if target > current:
        return min(target, current + max_delta)
    return max(target, current - max_delta)


def mixed_air_temp_c(oat_c: float, rat_c: float, oa_damper_pct: float) -> float:
    """Outside air and return air blend in proportion to the damper position."""
    fraction = oa_damper_pct / 100.0
    return oat_c * fraction + rat_c * (1 - fraction)


# Actuators (dampers, valves, the fan/VFD) move at a bounded rate, not instantly. This
# single constant is what keeps every loop below from bang-bang oscillating — see
# ramp_toward's docstring for how that was actually found (by running the loop, not by
# reading the functions). Tuned for a demo to actually settle within a couple of real
# minutes rather than the tens of minutes a gentler, more "realistic" rate would take.
ACTUATOR_SLEW_PCT_PER_TICK = 6.0

# Gains below were tuned empirically (grid-searched, then verified over thousands of
# ticks) against ACTUATOR_SLEW_PCT_PER_TICK and a 2-second tick — not first-principles
# loop tuning. Changing the tick interval or slew rate means re-tuning these. The
# cooling+economizer path settles into a small bounded hunt (~±0.16°C) rather than a
# perfect lock — realistic enough to leave alone rather than over-tune away.
SAT_PID_KP = 20.0
SAT_PID_KI = 0.1
FAN_PID_KP = 15.0
FAN_PID_KI = 0.5

# A fully open heating or cooling coil can swing the mixed air this many degrees C.
COIL_MAX_DELTA_C = 15.0
# How much of the gap between the duct's current temp and its physical "target" (mixed
# air + coil effect) closes per tick — the duct/airstream's own thermal lag.
SAT_RESPONSE_RATE = 0.3


# --- Generic PI controller, reused for the SAT loop and the static-pressure loop ----
@dataclass
class PIController:
    kp: float
    ki: float
    output_min: float = 0.0
    output_max: float = 100.0
    _integral: float = field(default=0.0, init=False, repr=False)

    def step(self, error: float, dt_s: float) -> float:
        # Anti-windup: clamp the integral so ki * integral alone can never exceed the
        # output range — not output_max itself, which (for small ki) would cap the
        # integral's contribution far below what's needed to ever close a steady error.
        self._integral += error * dt_s
        if self.ki:
            bound = abs(self.output_max - self.output_min) / abs(self.ki)
            self._integral = max(-bound, min(bound, self._integral))
        output = self.kp * error + self.ki * self._integral
        return max(self.output_min, min(self.output_max, output))

    def reset(self) -> None:
        """Zero the integral — call this when the equipment it drives gets shut off,
        so it doesn't wake up with a stale windup term from hours ago."""
        self._integral = 0.0


def split_range_valves(net_output_pct: float) -> tuple[float, float]:
    """Split one signed PI output into (heating_pct, cooling_pct).

    net_output_pct > 0 calls for heat, < 0 calls for cooling — the classic split-range
    convention so a single loop can't call for both at once.
    """
    heating = max(0.0, net_output_pct)
    cooling = max(0.0, -net_output_pct)
    return heating, cooling


# --- Duct static pressure / fan curve -------------------------------------------------
PRESSURE_AT_FULL_SPEED_INWC = 2.0


def fan_curve_pressure_inwc(fan_speed_pct: float, disturbance: float = 1.0) -> float:
    """A fan's pressure rise is roughly proportional to the square of its speed.

    `disturbance` stands in for VAV dampers opening/closing (which change system
    resistance) until real VAVs exist — see step_return_air_temp_c's docstring.
    """
    return (fan_speed_pct / 100.0) ** 2 * PRESSURE_AT_FULL_SPEED_INWC * disturbance


# --- AHU-1 plant: the sequence of operation's per-tick orchestration ----------------
class Ahu1Plant:
    """Everything the sequence of operation needs to remember between ticks, plus the
    mode-dependent branching (fan running vs. off, which PI loops reset) that composes
    the pure functions above into one tick's worth of physics.

    Moved here from main.py (originally this class's own docstring claimed "all the
    actual decisions are the pure functions in control.py," which wasn't true of the
    branching in `step` itself — the ordering and mode-dependent logic is exactly where
    a sequence-of-operation bug tends to live, and it was previously untested). main.py
    now only wires this into BACnet objects and an asyncio loop.

    `time_accel_x` and `rng` are injected (not read from env/module-global) so tests can
    run a real sim day in a handful of ticks and get deterministic fan-curve noise.
    """

    def __init__(
        self,
        *,
        time_accel_x: float = 180.0,
        sim_start_hour: float = 7.5,
        rng: random.Random | None = None,
    ) -> None:
        self.time_accel_x = time_accel_x
        self.rng = rng if rng is not None else random.Random()
        self.sim_seconds = sim_start_hour * 3600.0
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
        self.sim_seconds += dt_s * self.time_accel_x
        hour_of_day = (self.sim_seconds / 3600.0) % 24.0
        mode = schedule_mode(hour_of_day)
        fan_running = mode in ("occupied", "warmup")
        oat_c = outside_air_temp_c(hour_of_day)

        self.fan_curve_disturbance = max(
            0.85, min(1.15, self.fan_curve_disturbance + self.rng.uniform(-0.01, 0.01))
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
