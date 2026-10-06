# BACnet Points List

## AHU-1, device instance 10001

| Object type | Instance | Object name | Units | Writable | Description |
|---|---|---|---|---|---|
| Multi-state Value | 1 | `AHU1-OCC-MODE` | — (Occupied/Unoccupied/Warm-up) | no | Occupancy schedule state, M3 |
| Analog Value | 1 | `AHU1-SAT-SP` | degreesCelsius | yes (commandable) | Supply Air Temp setpoint |
| Analog Input | 1 | `AHU1-SAT` | degreesCelsius | no | Supply Air Temp — PI-loop controlled, M3 |
| Analog Input | 2 | `AHU1-OAT` | degreesCelsius | no | Outside Air Temp, simulated day/night curve |
| Analog Input | 3 | `AHU1-RAT` | degreesCelsius | no | Return Air Temp — a lumped "virtual zone" proxy until VAVs exist |
| Analog Output | 3 | `AHU1-HEATING-VALVE` | percent | yes (commandable) | Heating valve position, M3 PI loop output |
| Analog Output | 2 | `AHU1-COOLING-VALVE` | percent | yes (commandable) | Cooling valve position, M3 PI loop output |
| Analog Output | 4 | `AHU1-OA-DAMPER` | percent | yes (commandable) | Outside air damper — economizer-controlled, M3 |
| Analog Value | 2 | `AHU1-STATIC-PRESSURE-SP` | inchesOfWater | yes (commandable) | Duct static pressure setpoint |
| Analog Input | 4 | `AHU1-STATIC-PRESSURE` | inchesOfWater | no | Duct static pressure — fan-curve simulated |
| Analog Output | 1 | `AHU1-FAN-SPEED` | percent | yes (commandable) | Supply fan speed, M3 PI loop output |
| Binary Output | 1 | `AHU1-FAN-COMMAND` | — (active/inactive) | yes (commandable) | Supply fan command — occupancy-scheduled; the M4 fire interlock will override this at a higher BACnet priority |
| Binary Input | 1 | `AHU1-FAN-STATUS` | — (active/inactive) | no | Supply fan status — mirrors the command in this sim; a real status point comes from a separate sensor, so command/status mismatch is a real alarm condition (M6) |

Every object already carries its name, type, and units on the wire (`ReadProperty` for
`objectName`/`units` works against the live device) — this table exists anyway because a
real BAS submittal always ships one, and the gateway should agree with the device, not
just trust it.

## Planned (not yet implemented)

- **VAV-101..104**: Zone Temp, Zone Setpoint, Damper Position, Reheat Valve, Airflow —
  same pattern as AHU-1 (one more object, one more line here), held back because the
  sequences they'd drive (zone-level cooling/reheat, SAT reset from zone demand) need them
  to exist first.
- **Filter Alarm** (Binary Input): a simple threshold/fault point, natural fit for the M6
  alarm engine rather than built in isolation now.

## Implementation notes

- Simulator: `sims/bacnet_devices/main.py` (BACnet wiring) + `control.py` (the pure,
  unit-tested control math — PI loops, economizer, schedule, thermal lag). Gateway client:
  `gateway/app/bacnet_ahu.py`.
- Library: **bacpypes3 0.0.110**, direct — not BAC0. BAC0 is built on bacpypes3 but is
  designed for scanning/reading other devices from a human-driven script; this project
  needs to *host* devices (as a BACnet/IP server), which is bacpypes3's own
  `NormalApplication` + `bacpypes3.local.*` object classes.
- Addressing: no BACnet discovery (Who-Is/I-Am) yet — the gateway talks directly to
  AHU-1's known container IP (`10.10.0.11:47808`). Device discovery is a reasonable stretch
  item once there's more than one device to find.
- `ReadProperty`/`WriteProperty` both take a `bacpypes3.primitivedata.ObjectIdentifier`,
  not a raw `("analogInput", 1)` tuple — wrap it first
  (`ObjectIdentifier(("analogInput", 1))`), or `Application.read_property` raises
  `TypeError: objid`.
- A remote `ReadProperty` on a binary/multi-state object comes back as a plain int (0/1,
  or the 1-based state index), not the friendlier `BinaryPV`/state-text string a *local*
  object access gives you — the gateway maps these back to readable labels itself
  (`gateway/app/bacnet_ahu.py`'s `_format_value`), matching `main.py`'s own state tables.
- BACnet's `REAL` type is a 32-bit float, so a round-tripped value can come back as
  `14.199999809265137` instead of `14.2` — expected, not a bug; round for display.
- The gateway polls AHU-1's 13 points with 13 sequential `ReadProperty` calls per cycle.
  `ReadPropertyMultiple` would batch these into one request — worth doing once there's a
  second BACnet device to justify it, not optimized prematurely for one AHU on localhost.
- A cold `docker compose up` can have the gateway's first poll race AHU-1 still starting;
  without an explicit timeout that `await` can hang far longer than a poll cycle ever
  should (found by actually cold-starting the stack, not by reading the request path) —
  see `READ_TIMEOUT_S` in `bacnet_ahu.py`.
