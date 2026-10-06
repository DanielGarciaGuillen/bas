# Fire Alarm Notes

> ⚠️ **This is a simulation for learning and portfolio purposes only.** Real fire alarm
> systems are life-safety systems governed by the Fire Code and CAN/ULC standards —
> **S524** (installation), **S536** (inspection & testing), **S537** (verification), and
> **S1001** (integrated testing) — and must only be worked on by qualified, registered
> fire alarm technicians. Nothing here should be taken as guidance for real systems.

## Panel states

| State | Meaning |
|---|---|
| `NORMAL` | No active condition |
| `ALARM` | A device (smoke detector, pull station, flow switch) has activated |
| `TROUBLE` | A fault condition (e.g. wiring, device offline) |
| `SUPERVISORY` | A supervisory condition (e.g. sprinkler valve tamper) |

When more than one zone has a condition, the panel's overall/annunciated state is the
highest-priority one present: `ALARM` > `TROUBLE` > `SUPERVISORY` > `NORMAL` — an alarm
is never hidden behind a lesser condition. See `sims/fire_panel/panel.py`'s
`overall_condition()`.

## Panel functions

- **Acknowledge** — operator acknowledges the active condition. A *new* condition clears
  any existing acknowledge/silence (a fresh alarm demands fresh attention, even if an
  older one was already quieted).
- **Silence** — silences local audible notification (does not clear the condition).
- **Reset** — returns the panel to `NORMAL`, but only once every zone's *field device*
  has itself returned to normal (smoke cleared, pull station restored). Resetting while a
  zone is still active is rejected (HTTP 409 from the sim, with a message naming the
  blocking zone(s)) — matching real practice: you cannot reset a panel while a detector is
  still physically in alarm.

## Simulated zones / devices

1. Smoke detector — Lobby
2. Smoke detector — Office Area
3. Pull station — Main Entrance
4. Duct smoke detector (AHU-1) / sprinkler flow switch — grouped onto one zone, the way a
   real conventional panel wires multiple devices onto one zone circuit

## Interlock: AHU-1 fan shutdown

Implemented in M4. The gateway polls the fire panel sim (`gateway/app/fire_panel.py`)
every 2 seconds. Whenever **any** zone is in `ALARM`:

1. The gateway writes AHU-1's `AHU1-FAN-COMMAND` to **inactive** and `AHU1-OA-DAMPER` to
   **0%**, both at **BACnet priority 1** — see `docs/bacnet-points-list.md` and
   `gateway/app/bacnet_ahu.py`'s `engage_fire_interlock()`.
2. AHU-1's own schedule keeps writing its normal commands underneath, at the default
   priority (16) — but priority 1 always wins, so the interlock holds regardless of what
   the schedule thinks it's doing. This is BACnet's own priority-array mechanism, not
   custom logic the gateway invented — see the console's Notes tab, M4 module, for how
   that was verified.
3. The write is **idempotent and re-sent every poll cycle**, not edge-triggered on the
   alarm first appearing — simpler, and self-healing if the gateway restarts mid-alarm.

Once every alarmed zone's field device clears and the panel is reset back to `NORMAL`,
the gateway **relinquishes** priority 1 (`release_fire_interlock()`) and AHU-1's own
schedule immediately regains control — exactly the sequence `docs/sequences-of-operation.md`
§6 and §7 describe.

The console's Live tab shows this as `ahu-1.fire_interlock` (`active`/`inactive`) — a
synthetic point the gateway creates, not something read off a real BACnet object — so the
interlock's state is visible without needing to cross-reference the fan/damper points by
hand.

> Real world: see the disclaimer at the top of this file. A real fan-shutdown interlock
> is part of the fire alarm system's own engineered, often hardwired interlock to the
> HVAC controls, not application software running in a BAS gateway — and the valve
> positions this sim still computes while the fan sits off (see §7 of
> `sequences-of-operation.md`) are exactly the kind of detail a real commissioning review
> would catch and a real controller's own fire-aware sequence would not have.
