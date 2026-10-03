# BuildingOps Lab

A simulated small office building — HVAC, an energy meter, a fire alarm panel, and access
control — speaking real industrial protocols (BACnet/IP and Modbus TCP), normalized by a
gateway, and visualized in a React operator console with live graphics, trends, alarms, and
work orders.

Built as a portfolio project while moving from React/React Native development into
building automation (BAS), fire alarm, and low-voltage/security work in Ottawa–Gatineau.

**Everything here is simulated. No real equipment, no internet exposure.**

> ⚠️ This project is for learning and portfolio purposes only. Real fire alarm systems are
> life-safety systems governed by the Fire Code and CAN/ULC standards (S524, S536, S537,
> S1001) and must only be worked on by qualified, registered technicians. See
> [`docs/fire-alarm-notes.md`](docs/fire-alarm-notes.md).

## Status

🚧 Under construction — see milestones below.

- [x] M0: Repo skeleton, Docker Compose, docs stubs
- [x] M1: Modbus energy meter sim + gateway reading it (`docker compose up modbus-meter gateway`, then `curl localhost:8000/points`)
- [x] M2: BACnet AHU-1 (read + write) — `docker compose up modbus-meter bacnet-devices gateway`, then `curl -X POST localhost:8000/ahu-1/setpoint -d '{"value": 22.0}'` and watch `ahu-1.sat` drift toward it in `GET /points`

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full breakdown. At a glance:

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
                    Floor plan · AHU graphic · Trends · Alarms · Fire panel ·
                    Access log · Work orders · Network diagram
```

## Running it

```
docker compose up
```

Console will be at `http://localhost:5173` once M7 lands (not yet implemented).

## Docs

- [`docs/architecture.md`](docs/architecture.md) — how the pieces fit together
- [`docs/sequences-of-operation.md`](docs/sequences-of-operation.md) — HVAC control logic in plain English
- [`docs/network-design.md`](docs/network-design.md) — VLANs, IP plan, ports & firewall rules
- [`docs/modbus-register-map.md`](docs/modbus-register-map.md) — energy meter register map
- [`docs/bacnet-points-list.md`](docs/bacnet-points-list.md) — BACnet points list (like a real BAS submittal)
- [`docs/fire-alarm-notes.md`](docs/fire-alarm-notes.md) — panel states, interlock, standards disclaimer
- [`docs/learning-log.md`](docs/learning-log.md) — concepts learned, interview talking points

## Tech stack

| Layer | Choice |
|---|---|
| Device simulators | Python 3.12, BAC0/bacpypes3, pymodbus |
| Fire alarm & access sims | Python (FastAPI/asyncio) |
| Gateway | Python FastAPI, SQLite, asyncio |
| Frontend | React + TypeScript + Vite, Recharts, SVG |
| Orchestration | Docker Compose |
| Tests | pytest, Vitest |

## What I learned

See [`docs/learning-log.md`](docs/learning-log.md) — filled in milestone by milestone.

## Project summary (resume-ready)

_To be filled in at M10._
