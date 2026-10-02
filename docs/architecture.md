# Architecture

_Status: stub — to be filled in as the gateway and sims take shape (M1–M6)._

## Overview

```
 ┌───────────────────────── Docker network "bas_net" ─────────────────────────┐
 │                                                                           │
 │  [AHU-1 BACnet device]   [VAV-101..104 BACnet devices]   [Meter Modbus]   │
 │          │                         │                         │            │
 │          └────── BACnet/IP UDP 47808 ──────┐        Modbus TCP 502        │
 │                                            ▼                 │            │
 │  [Fire Alarm Panel sim]  ──REST/events──► [Gateway (FastAPI)] ◄┘           │
 │  [Access Control sim]    ──REST/events──►   • polling + COV-like updates  │
 │                                             • point tagging (Haystack)     │
 │                                             • alarm engine + interlocks    │
 │                                             • history (SQLite)             │
 │                                             • work orders (CMMS-lite)      │
 │                                             • WebSocket + REST API         │
 │                                                     │                      │
 └─────────────────────────────────────────────────────┼──────────────────────┘
                                                       ▼
                                   [React + TypeScript Operator Console]
```

## Components

| Component | Responsibility | Status |
|---|---|---|
| `sims/bacnet_devices` | AHU-1 + VAV-101..104, each a BACnet/IP device | not started |
| `sims/modbus_meter` | Energy meter over Modbus TCP | not started |
| `sims/fire_panel` | Fire alarm panel state machine over REST/events | not started |
| `sims/access_control` | Door/reader/cardholder sim over REST/events | not started |
| `gateway` | Polling, tagging, alarms, history, work orders, API | not started |
| `console` | React operator console | not started |

## Point model

The gateway normalizes every point (BACnet object, Modbus register, fire/access event)
into one shape:

```
{ id, device, objectType, instance, name, value, units, status, tags[] }
```

See [`bacnet-points-list.md`](bacnet-points-list.md) and
[`modbus-register-map.md`](modbus-register-map.md) for the concrete point/register
inventories, and [`sequences-of-operation.md`](sequences-of-operation.md) for the control
logic driving these points.

## Network topology

The lab runs on a single Docker bridge network (`bas_net`, `10.10.0.0/24`) for simplicity.
[`network-design.md`](network-design.md) documents the realistic multi-VLAN design this
would map to in an actual building.
