# Architecture

## Overview

```
 ┌─────────────────────────── Docker network "bas_net" ───────────────────────────┐
 │                                                                                │
 │  [AHU-1 BACnet]   [Meter Modbus]   [Fire Panel REST]   [Access Control REST]  │
 │        │                │                 │                     │             │
 │        └── :47808 ──────┼── :502 ─────────┼── :8001 ────────────┼── :8002     │
 │                          ▼                 ▼                     ▼            │
 │                       [Gateway (FastAPI) :8000]                               │
 │                         • polls all four, normalizes into one point shape     │
 │                         • fire alarm → AHU-1 fan/damper interlock             │
 │                         • alarm engine · SQLite history · work orders         │
 │                         • REST API (+ write/demo endpoints)                   │
 │                                        │                                     │
 └────────────────────────────────────────┼─────────────────────────────────────┘
                                          ▼
                       [React + TypeScript Console :5173]
       Overview · AHU-1 · Fire Panel · Access · Alarms · Trends · Points · Notes
                         — eight tabs, each its own poll loop
```

VAV-101..104 aren't built yet — see `bacnet-points-list.md` and the console's Notes tab.

## Components

| Component | Responsibility | Status |
|---|---|---|
| `sims/bacnet_devices` | AHU-1: BACnet/IP device with a real sequence of operation (`control.py`) | M2/M3 |
| `sims/modbus_meter` | Energy meter over Modbus TCP (one register: kW) | M1 |
| `sims/fire_panel` | Fire alarm panel FSM over REST (`panel.py`), now with an event log | M4/M8 |
| `sims/access_control` | Door/cardholder access-decision FSM over REST (`access.py`) | M5 |
| `gateway` | Polls all of the above, normalizes into one point shape, drives the fire interlock, runs the alarm engine + trend history + work orders, serves REST | M1–M6 |
| `console` | React operator console: eight dedicated tabs | M1–M8 |

## Console tabs (M7/M8)

| Tab | Shows |
|---|---|
| Overview | Occupancy mode, energy now, active alarm count, fire panel condition, door status — building-level signals, not a per-zone floor plan (no VAV zones exist; see `engineering-notes.md`) |
| AHU-1 | SVG schematic (OA damper → filter → cooling/heating coils → fan → supply duct) with live values, an animated fan tied to `fan_status`, and the SAT setpoint write form |
| Fire Panel | Zone LEDs, acknowledge/silence/reset, AHU-1 interlock status, event history, and the fire-trigger demo controls |
| Access | Door status tiles, badge/force/hold-open/clear demo controls, a live event log, and the cardholder list |
| Alarms | A sortable (by priority or newest) alarms table plus the work orders list — see `alarm-engine-notes.md` |
| Trends | One point, one time range, a hand-rolled SVG line chart reading `GET /history/{point_id}` |
| Points | The raw normalized points table, for debugging |
| Notes | Engineering notes, folded into the app milestone by milestone |

## Alarm engine, history, work orders (M6)

The gateway's supervisor loop (`gateway/app/supervisor.py`) ticks every few seconds,
evaluating the current point snapshot against a fixed rule set (`alarms.py`) and writing
every numeric point to a SQLite trend table (`db.py`). Alarms carry a real lifecycle
(`active_unacked → active_acked → cleared`) and can spawn a work order (`work_orders.py`)
that tracks the problem through to resolution. See
[`alarm-engine-notes.md`](alarm-engine-notes.md) for the rules, the lifecycle, and what was
deliberately deferred (a WebSocket push channel, bundled with M6 in the original plan).

## Point model

Every protocol normalizes into the same shape before it reaches the API or the console:

```
{ id, device, name, value, units, status }
```

`status` is `"ok"` or `"fault"` (a poll that failed keeps the last known shape with
`value: null`). `device` groups points by their source (`ahu-1`, `meter-1`, `fire-panel`,
`access-control`) and is what the console's Live tab uses to label each row's protocol.
See `gateway/app/state.py` and each poller module (`modbus_meter.py`, `bacnet_ahu.py`,
`fire_panel.py`, `access_control.py`) for the concrete shape.

See [`bacnet-points-list.md`](bacnet-points-list.md) and
[`modbus-register-map.md`](modbus-register-map.md) for the concrete point/register
inventories, and [`sequences-of-operation.md`](sequences-of-operation.md) for the control
logic driving them.

## The fire interlock, architecturally

The interlock (`docs/fire-alarm-notes.md`) lives in the **gateway**, not in AHU-1's own
sequence — it overrides AHU-1's fan/damper *output* points from outside, via BACnet's
priority array, rather than teaching the AHU's own controller code about the fire panel.
That's a deliberate boundary: AHU-1's sequence of operation only ever knows about its own
setpoints and measured values, the same way a real field controller doesn't know *why* an
interlock input changed, only that it did.

## Network topology

The lab runs on a single Docker bridge network (`bas_net`, `10.10.0.0/24`) for simplicity.
[`network-design.md`](network-design.md) documents the realistic multi-VLAN design this
would map to in an actual building.
