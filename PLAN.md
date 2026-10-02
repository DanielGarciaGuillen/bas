# Weekend Project Plan: "BuildingOps Lab", a Smart Building Operations Console

> **For Claude Code:** This file is the brief for a weekend portfolio project. Read it fully before writing code. Work milestone by milestone, commit after each one, and keep the README updated as you go. When a library API is uncertain, check its current docs or source before coding. Do not guess.

---

## 1. Why this project exists

**Owner:** Daniel Garcia Guillen, a React/React Native developer (about 7 years at Ross Video) moving into **building automation (BAS), fire alarm, security/low-voltage, and building operations (CMMS)** work in Ottawa–Gatineau.

**Currently studying:** CompTIA Network+ and the CFAA Fire Alarm Technician program.

**Goals**
1. **Showcase:** a portfolio piece that tells BAS integrators (Siemens, Johnson Controls, Ainsworth, BGIS, Régulvar) and facilities employers: *"I already understand your systems, protocols, and networks, and I can build the graphics and integrations."*
2. **Learn:** every module teaches a real concept Daniel will be asked about in interviews (BACnet objects, sequences of operation, fire alarm states, VLAN design, alarm handling, work orders).

**One-line pitch for the README:**
*A simulated small office building (HVAC, energy meter, fire alarm panel, and access control) with real industrial protocols (BACnet/IP and Modbus TCP), a gateway that normalizes and tags every point, and a React operator console with live graphics, trends, alarms, and work orders.*

---

## 2. Scope at a glance

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

**Everything is simulated. No real equipment, no internet exposure.**

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Device simulators | Python 3.12, **BAC0** (or **bacpypes3** directly), **pymodbus** | Check current BAC0 docs first; recent versions are async and built on bacpypes3. If running several BACnet devices proves painful, fall back to one simulator process hosting several devices, each on its own container IP. Document whatever you choose. |
| Fire alarm & access sims | Python (FastAPI or plain asyncio) | Event-driven state machines exposed over REST/WebSocket |
| Gateway | Python **FastAPI**, SQLite (SQLModel or sqlite3), asyncio tasks | Single source of truth for the UI |
| Frontend | **React + TypeScript + Vite**, a light charting lib (e.g. Recharts), plain SVG for graphics | This is Daniel's strength, so make it look professional |
| Orchestration | **Docker Compose** | `docker compose up` must bring up the whole lab |
| Tests | pytest (gateway logic), Vitest (a few UI units) | Focus tests on sequences, alarms, interlocks |

---

## 4. The simulated building

**"Lab Building," a 1-storey office with 4 zones.**

### 4.1 HVAC (BACnet/IP)
- **AHU-1** (one BACnet device): objects
  - `AI` Supply Air Temp (SAT), Return Air Temp (RAT), Outside Air Temp (OAT), Duct Static Pressure
  - `AO` Supply Fan Speed (%), Cooling Valve (%), Heating Valve (%), Outside Air Damper (%)
  - `BI` Supply Fan Status, Filter Alarm
  - `BO` Supply Fan Command
  - `AV` SAT Setpoint, Static Pressure Setpoint
  - `MV` Occupancy Mode (Occupied / Unoccupied / Warm-up)
- **VAV-101 to VAV-104** (one BACnet device each): Zone Temp (`AI`), Zone Setpoint (`AV`), Damper Position (`AO`), Reheat Valve (`AO`), Airflow CFM (`AI`)
- **Physics:** a simple first-order thermal model per zone (heat gain from occupancy and outside temp, cooling from supply air × damper). Plausible values matter more than accuracy. Include a "time acceleration" setting so a day plays out in a few minutes.

### 4.2 Energy meter (Modbus TCP)
- Holding/input registers: kW, kWh total, voltage, current, power factor. Document the register map in `docs/modbus-register-map.md`.

### 4.3 Fire alarm panel (simulated, conventional + addressable concepts)
- 4 zones / devices: smoke detectors, a pull station, a duct smoke detector on AHU-1, sprinkler flow switch.
- **States:** `NORMAL`, `ALARM`, `TROUBLE`, `SUPERVISORY`. Panel functions: acknowledge, silence, reset (reset only when the device is cleared).
- **Interlock:** when any fire ALARM is active, the gateway commands **AHU-1 supply fan OFF** and closes the OA damper (a common fan-shutdown sequence), and logs it. Alarm reset returns AHU control to normal.
- ⚠️ README must state: *simulation for learning only; real fire alarm systems are life-safety systems governed by the Fire Code and CAN/ULC standards (e.g. S524 installation, S536 inspection & testing, S537 verification, S1001 integrated testing) and must only be worked on by qualified, registered technicians.*

### 4.4 Access control (simulated)
- 3 doors (Main Entrance, Server Room, Mechanical Room), card readers, 6 fake cardholders with access levels and schedules.
- **Events:** access granted, access denied (wrong level / outside schedule), door forced open, door held open > 30 s.
- Forced/held events raise alarms in the gateway.

---

## 5. Gateway features

1. **Polling & normalization:** poll BACnet devices (ReadProperty / ReadPropertyMultiple) every few seconds, read Modbus registers, subscribe to fire/access events. Normalize everything into one point model:
   `{ id, device, objectType, instance, name, value, units, status, tags[] }`
2. **Tagging:** apply **Project Haystack-style tags** (e.g. `ahu`, `vav`, `zone`, `air`, `temp`, `sensor`, `sp`, `cmd`, `elec`, `meter`). Expose `GET /points?tags=zone,temp,sensor`. Add a short doc explaining what tagging solves.
3. **History:** store trend samples in SQLite; `GET /history/{pointId}?from&to`.
4. **Sequences of operation (the core learning piece):** implement and **write up in plain English** in `docs/sequences-of-operation.md`:
   - Occupied/unoccupied scheduling
   - VAV cooling: damper modulates on zone temp vs setpoint (simple PI loop); reheat when below setpoint at minimum airflow
   - AHU: SAT reset based on zone demand; duct static pressure control via fan speed (PI)
   - Economizer: use outside air for free cooling when OAT < RAT and within limits
   - Fire alarm fan shutdown (above)
5. **Alarm engine:** configurable rules (high/low limits with deadband and delay, status mismatch e.g. fan commanded ON but status OFF, filter alarm, fire/access events). Alarm lifecycle: `ACTIVE_UNACKED → ACTIVE_ACKED → CLEARED`. Priorities 1–4.
6. **Work orders (CMMS-lite):** button on an alarm → create a work order (asset, problem, priority, status Open/In progress/Done, notes). Small preventive-maintenance list (filter change every 90 days, fire alarm annual inspection). This links to CMMS/asset-data jobs.
7. **API:** REST + a WebSocket channel pushing point updates, alarms, and events. OpenAPI docs at `/docs`.

---

## 6. Operator console (React)

Pages / panels:
1. **Overview:** SVG floor plan with 4 zones colored by temperature vs setpoint, active alarm count, kW now, occupancy mode.
2. **AHU-1 graphic:** classic BAS-style SVG schematic (OA damper → filter → coils → fan → supply duct) with live values and animated fan; operator can change setpoints (writes go back through the gateway to BACnet `AV` objects).
3. **Zone detail:** VAV values, setpoint adjust, mini trend.
4. **Trends:** pick any point(s), time range, line chart.
5. **Alarms console:** sortable table, priority colors, acknowledge, "create work order."
6. **Fire panel annunciator:** zone LEDs (normal/alarm/trouble/supervisory), ack/silence/reset buttons, event history, interlock status ("AHU-1 shut down by fire alarm").
7. **Access control:** door status tiles, live event log, cardholder list.
8. **Work orders:** list + detail, PM schedule.
9. **Network:** a rendered diagram of the lab's network design (from §7) so the Network+ knowledge is visible.

**Design rules:** dark "control room" theme, clear units on every value, consistent alarm colors, keyboard accessible, works on a laptop screen. Use only original or generic graphics (no vendor logos or copied vendor UIs).

**Demo controls (sidebar "Simulation" panel):** trigger fire alarm on a zone, trigger trouble, force a door, change outside temperature, fail the supply fan status, speed up time. These make a 3-minute demo video easy.

---

## 7. Network design doc (Network+ showcase)

Write `docs/network-design.md` for a *realistic* small building network, even though the lab runs on one Docker network:
- VLAN plan: IT/corporate, BAS (BACnet/IP), Security (cameras/access), Fire alarm monitoring/annunciation (kept separate), Management.
- IP addressing table with subnets (e.g. /24s from 10.x.x.x), gateways, DHCP vs static (field controllers usually static).
- Ports & protocols table: BACnet/IP **UDP 47808**, Modbus TCP **502**, HTTPS 443, MQTT 1883/8883 (if used), SSH 22 (management only).
- Firewall rules between VLANs (least privilege: e.g. BAS VLAN → only the supervisor server; no internet from controllers).
- Notes on BACnet broadcast behaviour and BBMDs across subnets, PoE for cameras/readers, and basic OT security (default passwords, segmentation, remote access via VPN only).
- Include a diagram (Mermaid in Markdown is fine) and render it on the Network page.

---

## 8. Repository layout

```
buildingops-lab/
├─ docker-compose.yml
├─ README.md                 # pitch, screenshots/GIF, architecture, how to run, what I learned
├─ docs/
│  ├─ architecture.md
│  ├─ sequences-of-operation.md
│  ├─ network-design.md
│  ├─ modbus-register-map.md
│  ├─ bacnet-points-list.md   # points list like a real BAS submittal
│  ├─ fire-alarm-notes.md     # states, interlock, standards disclaimer
│  └─ learning-log.md         # Daniel's own notes, interview talking points
├─ sims/
│  ├─ bacnet_devices/         # AHU + VAVs
│  ├─ modbus_meter/
│  ├─ fire_panel/
│  └─ access_control/
├─ gateway/                   # FastAPI app, alarm engine, sequences, history, work orders
│  └─ tests/
└─ console/                   # React + TS + Vite
```

---

## 9. Weekend schedule & milestones

Commit at the end of each milestone. If running late, cut stretch items, not docs.

### Friday evening (2–3 h): Foundations
- [ ] M0: Repo, Docker Compose skeleton, README stub, `docs/` stubs
- [ ] M1: Modbus meter sim + gateway reading it (easiest protocol first; proves the pipeline)

### Saturday (6–8 h): Protocols & logic
- [ ] M2: BACnet AHU + VAV devices running; gateway reads all points; points list doc
- [ ] M3: Thermal model + sequences of operation (PI loops, economizer, scheduling) with unit tests
- [ ] M4: Fire alarm panel sim + fan-shutdown interlock + tests
- [ ] M5: Access control sim + events
- [ ] M6: Alarm engine, history, work orders, WebSocket

### Sunday (6–8 h): Console & polish
- [ ] M7: Console shell, Overview floor plan, AHU graphic with live values and setpoint writes
- [ ] M8: Alarms console, fire annunciator, access log, trends, work orders
- [ ] M9: Network page + network design doc
- [ ] M10: README with screenshots + 2–3 min demo GIF/video script, `learning-log.md` filled in

### Stretch (only if time remains)
- MQTT publishing of normalized points (IoT angle, relevant to cloud/smart-building roles)
- BACnet COV subscriptions instead of polling
- Simple fault detection rule (e.g. "simultaneous heating and cooling")
- French UI toggle (useful for Gatineau / Régulvar-type employers)

---

## 10. Acceptance criteria

- `docker compose up` starts everything; the console loads at `http://localhost:5173` (or documented port) with live values within 30 s.
- Changing a zone setpoint in the UI changes the BACnet `AV` value (verifiable with a BACnet explorer tool) and the zone temp responds.
- Triggering a fire alarm: annunciator shows ALARM, AHU-1 fan goes OFF in the graphic, the interlock is logged, and reset restores normal operation.
- Forcing a door raises a priority alarm; it can be acknowledged and turned into a work order.
- Gateway tests pass (sequences, alarm lifecycle, interlock).
- All docs in §8 exist and are written in plain, correct language Daniel can explain in an interview.

---

## 11. How Claude Code should work with Daniel (learning mode)

- **Explain as you build:** for each milestone, add 3–5 bullets to `docs/learning-log.md`: the concept, why it matters in real buildings, and one likely interview question with a short answer.
- **Let Daniel drive key pieces:** leave the sequences-of-operation write-up and the network VLAN table as drafts for Daniel to review and rewrite in his own words.
- **Be honest about simplifications:** mark anything that differs from real-world practice with a `> Real world:` note.
- **No secrets, no internet exposure, no vendor IP:** generic names only (e.g. "AHU-1", not a product name).

---

## 12. How this maps to the job targets

| Target role | What in this project proves it |
|---|---|
| Junior BAS Technician / Controls (Siemens, JCI, Ainsworth, BGIS) | BACnet objects & points list, sequences of operation, PI loops, setpoint writes, alarm handling |
| BAS Graphics / Integration / Systems Designer | AHU and floor-plan graphics, gateway normalization, Haystack tagging, REST/WebSocket integration |
| Fire Alarm Technician (CFAA trainee) | Panel states, ack/silence/reset logic, fan-shutdown interlock, standards awareness |
| Security / Low-Voltage / Access Control | Door events, forced/held alarms, access levels/schedules, segmented security VLAN |
| CMMS / Asset data / Facilities | Work orders from alarms, PM schedule, asset-based records |
| Network-heavy roles | Network design doc, VLAN/IP plan, ports & firewall rules (Network+) |

---

## 13. Final deliverables checklist

- [ ] Public GitHub repo with clear README, screenshots, and a demo GIF/video
- [ ] `docs/` folder complete
- [ ] 3-bullet project summary ready to paste into the resume "Projects" section
- [ ] LinkedIn post draft (short): what was built, what was learned, link to repo
