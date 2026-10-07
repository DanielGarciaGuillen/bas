# BuildingOps Lab

[![CI](https://github.com/DanielGarciaGuillen/bas/actions/workflows/ci.yml/badge.svg)](https://github.com/DanielGarciaGuillen/bas/actions/workflows/ci.yml)

A simulated small office building — HVAC, an energy meter, a fire alarm panel, and access
control — speaking real protocols (BACnet/IP, Modbus TCP), normalized by a gateway, and
exposed through a React console.

**Everything here is simulated. No real equipment, no internet exposure.**

> ⚠️ Simulation only. Real fire alarm systems are life-safety systems governed by the Fire
> Code and CAN/ULC standards, and must only be worked on by qualified, registered
> technicians. See [`docs/fire-alarm-notes.md`](docs/fire-alarm-notes.md).

## Status

M0–M8 done: Modbus meter, BACnet AHU-1 with a real PI-loop sequence of operation, a fire
alarm panel whose alarm shuts the AHU down via a BACnet priority override, access control
with per-door/per-cardholder access decisions, an alarm engine with trend history and work
orders, and an eight-tab operator console (Overview, AHU-1, Fire Panel, Access, Alarms,
Trends, Points, Notes). M9 (the network design page) is next. Design decisions and
debugging notes live in the console's **Notes** tab and
[`docs/engineering-notes.md`](docs/engineering-notes.md).

## Running it

```
docker compose up --build modbus-meter bacnet-devices fire-panel access-control gateway console
```

- Console: `http://localhost:5173` — Overview, an AHU-1 schematic with live values and
  setpoint writes, a fire panel annunciator, an access control panel, a sortable alarms +
  work orders view, a trend chart, a raw points table, and the Notes tab
- Gateway API docs: `http://localhost:8000/docs`

Local dev without Docker: `cd console && pnpm install && pnpm run dev`.

## Architecture

```
 [AHU-1 BACnet] [Meter Modbus] [Fire Panel REST] [Access Control REST]
                        └──────────► [Gateway :8000] ──► [Console :5173]
```

One Docker network stands in for what a real site splits across VLANs. Full breakdown:
[`docs/architecture.md`](docs/architecture.md).

## Docs

- [`docs/architecture.md`](docs/architecture.md) — how the pieces fit together
- [`docs/sequences-of-operation.md`](docs/sequences-of-operation.md) — HVAC control logic in plain English
- [`docs/network-design.md`](docs/network-design.md) — VLANs, IP plan, ports & firewall rules
- [`docs/modbus-register-map.md`](docs/modbus-register-map.md) — energy meter register map
- [`docs/bacnet-points-list.md`](docs/bacnet-points-list.md) — BACnet points list
- [`docs/fire-alarm-notes.md`](docs/fire-alarm-notes.md) — panel states, interlock, disclaimer
- [`docs/access-control-notes.md`](docs/access-control-notes.md) — doors, cardholders, access decisions
- [`docs/alarm-engine-notes.md`](docs/alarm-engine-notes.md) — alarm rules, lifecycle, work orders
- [`docs/engineering-notes.md`](docs/engineering-notes.md) — design decisions, debugging notes

## Tech stack

| Layer | Choice |
|---|---|
| Device sims | Python 3.12, bacpypes3, pymodbus |
| Gateway | Python, FastAPI |
| Console | React 19, TypeScript 7, Vite 8, pnpm |
| Lint/format | ruff (Python), oxlint + oxfmt (console) |
| Tests | pytest, Vitest |
| Orchestration | Docker Compose |

## Project summary (resume-ready)

_To be filled in at M10._
