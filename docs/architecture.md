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
 │                         • REST API (+ write/demo endpoints)                   │
 │                                        │                                     │
 └────────────────────────────────────────┼─────────────────────────────────────┘
                                          ▼
                       [React + TypeScript Console :5173]
                     Live points table · setpoint writes ·
                 fire/access demo controls · in-app Notes tab
```

VAV-101..104 aren't built yet — see `bacnet-points-list.md` and the console's Notes tab.

## Components

| Component | Responsibility | Status |
|---|---|---|
| `sims/bacnet_devices` | AHU-1: BACnet/IP device with a real sequence of operation (`control.py`) | M2/M3 |
| `sims/modbus_meter` | Energy meter over Modbus TCP (one register: kW) | M1 |
| `sims/fire_panel` | Fire alarm panel FSM over REST (`panel.py`) | M4 |
| `sims/access_control` | Door/cardholder access-decision FSM over REST (`access.py`) | M5 |
| `gateway` | Polls all of the above, normalizes into one point shape, drives the fire interlock, serves REST | M1–M5 |
| `console` | React Live-points monitor + in-app Notes tab | early (grows into the full M7 console) |

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
