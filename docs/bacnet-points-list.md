# BACnet Points List

## M2 (current) — AHU-1, device instance 10001

| Object type | Instance | Object name | Units | Writable | Description |
|---|---|---|---|---|---|
| Analog Value | 1 | `AHU1-SAT-SP` | degreesCelsius | yes (commandable) | Supply Air Temp setpoint |
| Analog Input | 1 | `AHU1-SAT` | degreesCelsius | no | Supply Air Temp (drifts toward setpoint — real control loop lands in M3) |
| Binary Input | 1 | `AHU1-FAN-STATUS` | — (active/inactive) | no | Supply fan running status (hardcoded `active` until M3 adds fan command/status) |

Unlike the Modbus register map, this table is almost redundant: every object already
carries its name, type, and units on the wire (`ReadProperty` for `objectName`/`units`
works against the live device). It's included anyway because a real BAS submittal always
ships one — the gateway should still agree with the device, not just trust it blindly.

## Planned (not yet implemented)

The rest of AHU-1's points (Return/Outside Air Temp, Duct Static Pressure, Cooling/Heating
Valve, OA Damper, Filter Alarm, Supply Fan Command, Static Pressure Setpoint, Occupancy
Mode) and VAV-101..104 (Zone Temp, Zone Setpoint, Damper Position, Reheat Valve, Airflow)
follow the same pattern: one more `Analog*`/`Binary*`/`MultiState*` object, one more line
here. Held back for M2 to prove the BACnet pipeline — read, write, and a live device
response — with the least code first.

## Implementation notes

- Simulator: `sims/bacnet_devices/main.py`. Gateway client: `gateway/app/bacnet_ahu.py`.
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
- BACnet's `REAL` type is a 32-bit float, so a round-tripped value can come back as
  `14.199999809265137` instead of `14.2` — expected, not a bug; round for display.
