# Sequences of Operation — AHU-1

_Status: M3 implemented, draft wording — Daniel to review and rewrite in his own words
(per PLAN.md §11). This is the core learning piece of the project: a sequence of operation
(SOO) is the plain-English spec a controls engineer writes and a technician/commissioning
agent verifies against. The tested, pure-math version of everything below lives in
`sims/bacnet_devices/control.py`; this file is the English translation of that code._

## 1. Occupancy schedule

AHU-1 runs a simple fixed daily schedule:

| Time | Mode |
|---|---|
| 07:00 – 08:00 | Warm-up |
| 08:00 – 18:00 | Occupied |
| 18:00 – 07:00 | Unoccupied |

The supply fan runs during Warm-up and Occupied, and is commanded off during Unoccupied —
the fan status point should always match the fan command; a mismatch is exactly the kind
of fault the alarm engine (M6) will flag.

> Real world: a real schedule is usually a weekly calendar with holiday exceptions,
> configured by the operator through the front end, not hardcoded. AHU-1's schedule is a
> single fixed daily pattern — the mechanism (a time-of-day lookup) is real, the
> configurability isn't, yet.

## 2. Supply air temperature control (the main loop)

A PI (proportional-integral) loop compares AHU1-SAT (measured supply air temp) against
AHU1-SAT-SP (the writable setpoint, adjustable from the console's Live tab). The loop's
single signed output is split into two valves so the AHU can never call for heating and
cooling at the same time (split-range control):

- Output > 0 → heating valve opens, cooling valve stays shut
- Output < 0 → cooling valve opens, heating valve stays shut

> Real world: a real AHU's SAT setpoint is often *reset* dynamically based on how hard the
> zones it serves are working (if every VAV damper is nearly closed, the AHU is
> overcooling and can raise its SAT setpoint to save energy — "trim and respond"). AHU-1
> has no VAVs yet, so the setpoint here is operator-set only. SAT reset is a natural
> follow-up once zones exist.

## 3. Economizer (free outside-air cooling)

When the fan is running, the loop is actually calling for cooling, and the outside air
is usefully colder than the return air (with a deadband so it doesn't hunt, and a low
limit so the coils don't risk freezing), the outside air damper opens wide instead of
running the mechanical cooling valve — free cooling. Otherwise the damper sits at a
ventilation minimum while the fan runs, and closes fully when it's off.

> Real world: real economizers often compare *enthalpy* (temperature + humidity), not just
> dry-bulb temperature, since a bone-dry 15°C day cools a building better than a humid
> 13°C one. AHU-1 only models temperature — no humidity sensor exists yet.

## 4. Duct static pressure control (the fan loop)

A second PI loop compares AHU1-STATIC-PRESSURE against AHU1-STATIC-PRESSURE-SP and drives
AHU1-FAN-SPEED to hold it. The fan's actual pressure follows a simple fan-curve model
(pressure rises with roughly the square of speed).

> Real world: a real duct system's resistance changes constantly as every VAV damper in
> the building opens and closes. AHU-1 stands that in with a small random "disturbance" on
> the fan curve rather than real VAV demand, since there are no VAVs yet to generate it.

## 5. Why two loops instead of one, and why they don't snap instantly

Both PI loops drive their actuators (valves, the OA damper, the fan) through a slew-rate
limit — an actuator moves toward its commanded position by a bounded amount per tick
rather than jumping there instantly. Removing that limit was tried during development: the
SAT loop oscillated forever, alternating between full heating and full cooling every tick,
because the economizer's on/off switching snapped the mixed-air temperature between two
extremes every cycle. A real damper or valve actuator takes time to travel for the same
reason — modeling that turned out to be load-bearing, not cosmetic. See the git history on
`sims/bacnet_devices/control.py` and its tests for the debugging trail.

## 6. Fire alarm fan shutdown (interlock) — M4

Not yet implemented. When built: any fire `ALARM` will command AHU-1's supply fan OFF and
the OA damper closed, logged as an interlock event, with control returning to normal on
reset. AHU1-FAN-COMMAND is already a *commandable* BACnet object (`AnalogOutputObject`/
`BinaryOutputObject` both carry BACnet's priority array) specifically so the M4 interlock
can override it at a higher priority without permanently clobbering the schedule's own
command — see the console's Learn tab, M2 module, for why that mechanism exists.

> Real world: see the disclaimer in `docs/fire-alarm-notes.md` — a real fan-shutdown
> sequence is part of the fire alarm system's engineered, often hardwired interlock, not
> application software running in a BAS controller.
