# Fire Alarm Notes

> ⚠️ **This is a simulation for learning and portfolio purposes only.** Real fire alarm
> systems are life-safety systems governed by the Fire Code and CAN/ULC standards —
> **S524** (installation), **S536** (inspection & testing), **S537** (verification), and
> **S1001** (integrated testing) — and must only be worked on by qualified, registered
> fire alarm technicians. Nothing here should be taken as guidance for real systems.

_Status: stub — to be filled in during M4 once `sims/fire_panel` is implemented._

## Panel states

| State | Meaning |
|---|---|
| `NORMAL` | No active condition |
| `ALARM` | A device (smoke detector, pull station, flow switch) has activated |
| `TROUBLE` | A fault condition (e.g. wiring, device offline) |
| `SUPERVISORY` | A supervisory condition (e.g. sprinkler valve tamper) |

## Panel functions

- **Acknowledge** — operator acknowledges the active condition.
- **Silence** — silences local audible notification (does not clear the condition).
- **Reset** — returns the panel to `NORMAL`; only possible once the field device condition
  has cleared.

## Simulated zones / devices

1. Smoke detector, Zone 1
2. Smoke detector, Zone 2
3. Pull station, Zone 3
4. Duct smoke detector on AHU-1 + sprinkler flow switch, Zone 4

## Interlock: AHU-1 fan shutdown

TODO (M4): document the exact interlock behavior and how it's logged. See
[`sequences-of-operation.md`](sequences-of-operation.md) §6.

> Real world: see the disclaimer at the top of this file.
