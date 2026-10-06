"""Pure control-logic functions for AHU-1's sequence of operation.

Kept separate from main.py (which only wires these into BACnet objects and an asyncio
loop) so the actual control math is unit-testable without a running BACnet stack. See
docs/sequences-of-operation.md for the plain-English version of each sequence.
"""

from __future__ import annotations

import math
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
