# Sequences of Operation

_Status: draft stub — Daniel to review and rewrite in his own words (per PLAN.md §11).
This is the core learning piece of the project: a sequence of operation (SOO) is the plain-English
spec a controls engineer writes and a technician/commissioning agent verifies against._

## 1. Occupied / unoccupied scheduling

- TODO: describe the weekly schedule, occupied/unoccupied/warm-up modes, and how `MV`
  Occupancy Mode on AHU-1 drives setback setpoints on the VAVs.

## 2. VAV cooling

- TODO: zone damper modulates on zone temp vs. setpoint error (PI loop).
- TODO: reheat valve logic when the zone calls for heat at minimum airflow.

## 3. AHU supply air temp reset

- TODO: SAT setpoint reset based on aggregate zone demand (trim & respond concept).

## 4. Duct static pressure control

- TODO: supply fan speed PI loop against the static pressure setpoint.

## 5. Economizer (free cooling)

- TODO: conditions for using outside air (OAT < RAT, within min/max OA damper limits).

## 6. Fire alarm fan shutdown (interlock)

- TODO: on any fire `ALARM`, gateway commands AHU-1 supply fan OFF and OA damper closed;
  logged as an interlock event; reset restores normal control.

> Real world: a real fan-shutdown sequence is part of the fire alarm system's engineered
> interlock (often hardwired or via a listed interface), not just application software in a
> BAS controller — life-safety functions are not allowed to depend solely on a non-listed
> gateway. This project simplifies that for demonstration.
