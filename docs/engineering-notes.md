# Engineering Notes

Design decisions, debugging trails, and why things are built the way they are, milestone
by milestone — kept here instead of scattered across commit messages.

## M0 — Foundations (repo skeleton, Docker Compose, docs)

- **Concept:** a BAS project is really a small distributed system — field devices, a
  supervisory/gateway layer, and an operator UI — connected by real industrial protocols,
  not just "an app." Laying out `sims/`, `gateway/`, `console/` as separate services wired
  by Docker Compose mirrors how a real site has physically separate controllers talking to
  a head-end/supervisor over a network.
- **Why it matters:** in a real building, the "gateway" role is played by a supervisory
  device or server (e.g. a JACE, a Niagara station, or a vendor's front-end server) that
  polls multiple protocols and presents one unified view to operators — exactly the job
  this gateway will do for BACnet, Modbus, and the fire/access REST feeds.
- **Why Docker Compose specifically:** it lets the whole simulated site — multiple "field
  devices" plus the gateway plus the console — come up with one command and talk to each
  other over an isolated virtual network, standing in for a real site's segmented VLANs
  (see `docs/network-design.md`).
## M1 — Modbus meter sim + gateway reading it

- **Concept:** Modbus TCP is function-code + address + register-count based — there's no
  notion of "named points" on the wire, just numbered registers (e.g. "read 1 input
  register starting at address 0"). The meaning of a register (what it is, its units, its
  scale factor) exists only in documentation — the register map — and both ends of the
  wire have to agree on it out of band. That's exactly what `docs/modbus-register-map.md`
  is for, and it's why real meter/BAS vendors publish one per product.
- **Scaling:** real meters very often pack a decimal value into a plain 16-bit integer
  register using a documented scale factor (register value ÷ 10 = kW here) rather than
  sending a float directly, since classic Modbus registers are just 16-bit words. Reading
  the raw register and dividing by the scale factor is the "decode" step every Modbus
  client has to implement per the vendor's register map.
- **Read-only vs. writable:** input registers (function code 0x04) are conventionally
  read-only measured values (what this meter exposes); holding registers (0x03/0x06/0x10)
  are read/write and typically hold configuration or setpoints. Coils and discrete inputs
  are the 1-bit equivalents.
- **Simplification:** cut the full register set (voltage, current, PF, kWh) down to just
  kW for M1, to prove the device → gateway → API pipeline with the least code possible.
  More registers are just "more of the same pattern" — see the "Planned" section in
  `docs/modbus-register-map.md`.
- **Pinned library version:** pymodbus's newest release (3.15.x) turned out to have
  replaced the simple, documented datastore API with a new config-driven simulator model
  mid-major-version — a reminder that "install the latest" isn't always right, especially
  for a library you're using in an unconventional way (as a long-running mutable server,
  not pymodbus's own intended "simulate fixed test data" use case). Checking the installed
  API via `python -c "...inspect.signature..."` before writing code against it caught this
  early instead of mid-debug.
## M2 — BACnet AHU-1 (self-describing points, read + write)

- **Concept:** BACnet objects describe themselves on the wire — type, name, units, status —
  where Modbus registers are just numbers the register map gives meaning to. Reading
  `objectName` and `units` straight off the device in `docs/bacnet-points-list.md`'s
  implementation notes made that difference concrete rather than theoretical.
- **Read vs. write:** `ReadProperty`/`WriteProperty` are genuinely symmetric services in
  BACnet — any property on any object can in principle be read or written, subject to
  whether the object is "commandable." That's a real architectural difference from Modbus,
  where read-only input registers and read/write holding registers are separate address
  spaces by convention, not by protocol enforcement.
- **Commandable objects:** a plain `AnalogValueObject` isn't automatically writable from the
  network — it needs the `Commandable` mixin (`AnalogValueObjectCmd`), which adds the
  priority-array machinery BACnet uses to arbitrate between multiple writers (an operator
  override vs. a schedule vs. a safety interlock, each at a different priority). Not needed
  yet with one writer, but it's the mechanism that later makes the fire alarm interlock
  (M4) able to override a setpoint without permanently clobbering it.
- **Simplification:** one device (AHU-1), three points (a writable setpoint, the measured
  value it drives, and a status point) — not the full AHU + 4-VAV point list from the
  original brief. Same reasoning as M1's single register: prove read+write+live-response
  first, then it's "more of the same pattern" for every other point.
- **Library choice:** bacpypes3 directly, not BAC0. BAC0 wraps bacpypes3 for the common
  case of *scanning* other people's devices; this project needs to *be* a device, which is
  bacpypes3's own lower-level territory. Confirmed by reading `bacpypes3/local/*.py`'s
  object classes and `bacpypes3/ipv4/app.py`'s `NormalApplication` before writing anything.
## Early console detour — a live points monitor, ahead of M3

Jumped ahead of the milestone order to get a visual check on the gateway instead of
curling `/points` by hand. Scoped deliberately small: one page, a live table, one
setpoint-write form — not the floor plan/AHU graphic/trends from the full M7 console,
which still needs M3-M6's concepts (zones, alarms, history) to mean anything.

- **Concept:** the console never touches BACnet or Modbus directly — it only ever talks to
  the gateway's REST API. That's the entire point of the normalized point model: the UI
  layer doesn't need to know or care that `ahu-1.sat` came from BACnet and `meter-1.kw`
  came from Modbus.
- **Why it matters:** this is the same reason a real BAS front-end (a Niagara station's
  web UI, a vendor's SCADA client) never speaks the field protocol itself — it talks to
  the supervisory layer's own API/database, which already did the protocol work.
- **A real CORS wrinkle:** the console (`localhost:5173`) and the gateway (`localhost:8000`)
  are different origins even on the same machine, so the browser blocks the fetch unless
  the gateway sends CORS headers. Caught immediately by actually loading the page in a
  browser rather than trusting that "the API works" (proven via `curl`) means "the UI
  works" — curl doesn't enforce CORS, browsers do.
- **Stack choice:** picked the actual current stable releases (React 19.3, Vite 8.3,
  TypeScript 7.0 — TS's new native/Go-based compiler) rather than assuming older
  tutorial-era versions, then verified the whole toolchain (`npm run build`: typecheck +
  bundle) before trusting it.
## Console hardening — adopting real project hygiene, and an in-app Notes tab

Re-architected the console to match the conventions of a production codebase (a personal
one, `ott-next`) rather than a quick prototype, and folded the build-notes content
directly into the app as a **Notes** tab (replacing a standalone page kept outside the
repo).

- **Concept:** `oxlint`/`oxfmt` are Rust-based (via the Oxc project) drop-ins for
  ESLint/Prettier — same job, startlingly faster, because they skip the JS AST entirely.
  Worth knowing as "the ecosystem moved" rather than assuming ESLint is still the default.
- **pnpm's `packageManager` field + Corepack:** pinning `packageManager: "pnpm@x.y.z"` in
  `package.json` means `corepack enable` downloads exactly that version on first use —
  nobody (including CI) can silently drift onto a different pnpm version.
- **Verifying before guessing:** `pnpm/action-setup`'s input for pointing at a non-root
  `package.json` is `package_json_file` (underscore), not the hyphenated form a GitHub
  Actions convention would suggest. Checked the action's actual `action.yml` via `gh api`
  rather than assuming the naming pattern — the same "check the source" habit that caught
  pymodbus's and pnpm's version quirks earlier.
- **Why fold the notes into the app:** a separate notes page is one more thing to keep in
  sync by hand every milestone. A `MODULES` array of React components next to the code it
  documents can't drift the same way a copy-pasted artifact can — and it ships with the
  project itself instead of living beside it.
- **Testable extraction:** pulled `protocolFor`/`formatValue` out of the table component
  into `lib/points.ts` purely so they'd have something to unit-test — the same "extract the
  pure decode step" pattern used for the gateway's Modbus/BACnet polling.

## M3 — Thermal model + sequences of operation

- **Concept:** a "sequence of operation" is firmware logic, and it runs *on the
  controller*, not on the supervisory layer. That's why `control.py`'s PI loops,
  economizer, and schedule live in `sims/bacnet_devices/` (the simulated AHU controller)
  rather than in the gateway — the gateway only ever reads measured values and writes
  setpoints/commands, exactly like a real BAS front end talking to a real field panel.
- **Split-range control:** one signed PI output (negative = cool, positive = heat) splits
  into two valve commands so the system structurally can't call for heating and cooling
  at once — a cheap, standard pattern (`split_range_valves`) worth knowing by name.
- **The bug that mattered most this milestone — integral windup, misdiagnosed twice:**
  first pass clamped the PI controller's integral term directly to the output range
  (`±100`). With a small `ki` (0.01), that capped the integral's *contribution* at `ki *
  100 = 1.0` — nowhere near enough to ever close a steady-state error, so the loop
  stabilized exactly 4°C off setpoint and stayed there forever. The fix: clamp the
  integral to `±(output_range / ki)`, the textbook anti-windup bound, so `ki * integral`
  alone can reach the output limit but no further.
- **The bug that mattered second most — a textbook limit cycle, found only by running the
  loop, not by reading it:** even after fixing the integral, a cooling scenario still
  wouldn't settle. The actual cause: the economizer's outside-air damper snapped instantly
  between 20% and 90% every single tick, and that swung the mixed-air temperature so hard
  each way that the SAT loop oscillated forever instead of converging — a real bang-bang
  limit cycle, invisible to a per-function unit test and only visible by simulating
  hundreds of ticks end to end. Fixed by giving every actuator (damper, valves, fan) a
  bounded slew rate (`ramp_toward`) — which is also just... how real actuators behave;
  they don't teleport. The fix was simultaneously "more correct physics" and "fixes the
  bug," which is a good sign the original model was missing something real, not just
  under-tuned.
- **A third, subtler bug — the economizer helping when it shouldn't:** first version of
  `economizer_oa_damper_pct` opened the OA damper whenever outside air was colder than
  return air, full stop. That's wrong: during an actual *heating* call, flooding the AHU
  with cold outside air fights the heating coil instead of helping anything. A real
  economizer only engages when the loop is *actually calling for cooling* — fixed by
  passing the loop's own cooling-demand signal into the economizer decision, not just
  comparing OAT/RAT in isolation.
- **Tuning for the medium, not just correctness:** the first stable gains took ~30-60
  minutes of (real) time to settle — technically convergent, useless for a demo video.
  Re-tuning for a few minutes of real-world settling time was its own deliberate step,
  separate from "does it converge at all." A working control loop and a *demoable* one
  aren't the same bar.
- **Decoupling the demo clock from the physics:** the occupancy schedule and outside air
  temperature run on an accelerated "sim day" (a full 24h cycle in minutes) so a demo
  doesn't have to wait for real 8am/6pm. The control loops themselves (PI math, actuator
  slew, thermal lag) deliberately do *not* get that acceleration — they run against the
  real tick interval, so the already-tested, real-time-tuned behavior stays exactly what
  was verified. Mixing "clock speed" and "physics speed" was tempting and would have been
  wrong: it would have meant re-deriving every gain for whatever acceleration factor got
  chosen.
- **A deployment bug the unit tests couldn't catch:** `sims/bacnet_devices/control.py` was
  a new file, and the Dockerfile only `COPY`'d `main.py` — the container built fine
  (Docker doesn't know what the Python file imports) and crashed instantly on start with
  `ModuleNotFoundError`. Unit tests ran on the host, against the real filesystem, so they
  never saw it. Caught only by actually running `docker compose up` with the real
  container, which is exactly why that step isn't optional before calling something done.
- **A second deployment bug, same root lesson:** on a true cold start, the gateway's very
  first BACnet `read_property` to AHU-1 raced the device still starting up — and hung
  indefinitely instead of raising, because nothing in the request path enforced a timeout
  short enough for a poll loop. Wrapped every read/write in `asyncio.wait_for(...)`. Two
  bugs in one milestone that only a real cold `docker compose up` surfaced — a reminder
  that "unit tests pass" and "the stack actually comes up from nothing" are different
  claims.
## M4 — Fire alarm panel + interlock

- **Concept:** a fire alarm panel is its own system, deliberately kept separate from the
  BAS — it doesn't speak BACnet or Modbus. Simulating it over plain REST (not a field
  protocol) is the point, not a shortcut: the gateway polls it the same *shape* it polls
  BACnet/Modbus, but the panel itself never pretends to be a field device.
- **Discovering BACnet's priority array actually solves the interlock problem for free:**
  before writing any interlock code, tested directly against the real AHU-1 objects
  whether a high-priority (`priority=1`) `WriteProperty` really does survive the
  schedule's ongoing low-priority (`priority=16`, the default) writes — it does, and
  *relinquishing* (writing `Null(())` at that priority, not a plain Python `None`, which
  doesn't cast) hands control straight back to whatever the schedule is currently doing.
  No "remember what the fan was doing before the alarm" logic needed anywhere — BACnet's
  own mechanism does that. Verified empirically with a throwaway client/server script
  before writing a line of `gateway/app/bacnet_ahu.py`, rather than assuming it would work
  from reading the spec/library docs.
- **The same shared-mutable-default bug, in a new disguise:** `Panel()`'s default zones
  were built from a module-level `DEFAULT_ZONES` list — reused by *reference*, not copied.
  One test's `trigger()` call mutated a `Zone` object that every other `Panel()` instance
  in the same process was secretly sharing, so tests passed alone and failed together.
  Same root cause as a mutable default argument, just one level removed (a shared default
  *factory* producing shared *contents*, not a shared default argument itself) — worth
  recognizing the pattern, not just the textbook version of it.
- **Keeping "clear" and "reset" as separate actions, on purpose:** a real panel can't be
  reset while a zone is still physically in alarm — clearing the smoke and resetting the
  panel are two different real-world events, and collapsing them into one action would
  hide a safety-relevant distinction. `sims/fire_panel/panel.py`'s `reset()` enforces this
  with a typed `ResetBlocked` exception (naming which zones are still active), surfaced to
  the console as an HTTP 409 — an error a demo can deliberately trigger and explain, not
  just a thing to avoid.
- **A known, documented gap left alone on purpose:** the interlock forces AHU-1's fan and
  damper off, but the AHU's own PI loops (unaware the fire panel exists) keep computing
  valve positions as if the fan were still running. Fixing that would mean teaching the
  AHU's sequence about the fire panel — exactly the boundary the interlock's own design
  (override from outside, via the priority array) was built to avoid crossing. Documented
  in `docs/sequences-of-operation.md` §7 instead of "fixed" by blurring that line.

## M5 — Access control

- **Concept:** access control is a third instance of the same boundary fire alarm already
  established — its own system, REST not a field protocol, polled by the gateway the same
  shape as everything else. By M5 this wasn't a new decision, just applying one already
  made twice.
- **No simulated clock here, on purpose:** AHU-1 runs an accelerated "sim day" so its
  schedule-driven behavior is demoable without waiting for real 8am/6pm. Access control
  doesn't — "business hours" is checked against the real wall-clock time. The difference:
  AHU-1 runs an autonomous simulation loop that needs a fast clock to be watchable; access
  control is purely event-driven (a badge attempt either happens or it doesn't), so there's
  no loop to accelerate and no reason to fake the clock it checks against.
- **The exact same shared-mutable-default bug, caught before it had the chance to bite:**
  `AccessControlSystem`'s `__post_init__` builds fresh `Door`/`Cardholder` instances rather
  than reusing `DEFAULT_DOORS`/`DEFAULT_CARDHOLDERS` directly — written that way from the
  start this time, because M4's `sims/fire_panel/panel.py` had already paid for the lesson.
  The test suite passed on the first run as a result, rather than passing in isolation and
  failing together the way the fire panel's did.
- **Choosing cardholders to cover every outcome, not just a happy path:** six cardholders
  were picked specifically to hit all five event results (`granted`, `denied_level`,
  `denied_schedule`, plus `forced`/`held_open` from the door side) — a facilities manager
  with blanket access, a 24/7 security guard with mid-tier access, a night cleaner capped
  at the front door, and day-shift staff who lose access the moment the clock passes 6pm.
  Designing the fixture data to exercise the state space is itself a design decision, not
  an afterthought.
- **Extracting the second real instance of a pattern, not the first:** the fire panel's
  demo-proxy endpoints in `gateway/app/main.py` were one-off functions; adding access
  control's gave a second, near-identical set, which is exactly the point where
  generalizing (one `_proxy()` helper, one `postJson()` helper on the console side) stops
  being premature abstraction and starts being the obvious move.

## M6 — Alarm engine, history, work orders

- **Concept:** up to M5 the gateway only ever reflected point state it polled — it never
  decided anything. M6 adds a real logic layer on top: an `AlarmEngine` that evaluates the
  same point snapshot every supervisor tick against a small fixed rule set (fire condition,
  forced/held-open doors, fan command/status mismatch, sustained SAT deviation), a SQLite
  trend store, and a `WorkOrderStore` an operator can create straight from an alarm. See
  `docs/alarm-engine-notes.md` for the rules and the state machine in detail.
- **Alarm lifecycle, not a boolean:** `active_unacked → active_acked → cleared`.
  Acknowledging an alarm only records that a human has seen it — the underlying condition
  (a door still forced, a zone still in alarm) is untouched. Clearing is the engine's own
  re-evaluation deciding the condition is actually gone. Collapsing those two into one flag
  would let an operator silence an alarm and have the system claim the problem was solved
  when it wasn't.
- **Each alarm key keeps exactly one active instance, but a full history:** re-raising the
  same condition after it clears opens a brand new alarm `id` rather than resurrecting the
  old row, which is what lets the alarm table double as an audit trail instead of only
  "what's wrong right now."
- **The SAT-deviation rule needed two conditions, not one:** a single noisy sample
  shouldn't page anyone, and the AHU-1 PI loop is *expected* to overshoot briefly after a
  setpoint step (M3). The rule tracks a per-point "deviation since" timestamp and only
  raises once the measured value has stayed outside a 2°C deadband continuously for 30
  seconds — resetting the timer the instant the point comes back inside the deadband.
  Verified with explicit unit cases for "inside the deadband never alarms," "outside the
  deadband but not long enough never alarms," and "recovering resets the clock," rather
  than trusting one live demo run to prove the logic.
- **An alarm that correctly never fired, live:** writing an aggressive setpoint step during
  manual testing never triggered the SAT alarm. Not a bug — the PI loop converged back
  inside the 2°C deadband before the 30-second delay elapsed, exactly what a well-tuned
  loop recovering from a legitimate setpoint change should do. The 12-case unit suite is
  what made it possible to tell "no alarm, correctly" apart from "broken alarm" instead of
  guessing from a single anecdote.
- **Pure-logic extraction, same pattern as every prior milestone:** `alarms.py` and
  `work_orders.py` take a plain `dict`/`datetime` snapshot in and return plain dataclasses
  out — no FastAPI, no sqlite, no I/O. That's what let both get a full unit suite (12 + 6
  cases) before either was wired into `main.py` at all, and both suites passed on the
  first run.
- **History and the supervisor loop are a separate concern from alarms, even though they
  share a tick:** `supervisor.py` runs one periodic loop that calls `alarm_engine.evaluate()`
  and `db.record_samples()` back to back on the same snapshot — not because they're
  logically coupled, but because polling the same `points` dict once per tick for two
  unrelated jobs is simpler than running two independent timers against state that can
  change underneath either one.
- **SQLite over anything heavier, on purpose:** trend history here is "a few numeric
  points, sampled every few seconds, queried by a demo UI" — not a production historian's
  workload. The stdlib `sqlite3` module via `asyncio.to_thread` (so a disk write never
  blocks the event loop) is the simplest thing that's actually correct for that scope; an
  ORM or a dedicated time-series database would be solving a problem this project doesn't
  have.

## M7 — Console shell, overview, AHU graphic

- **Concept:** up to M6 the console was one page (plus Notes). M7 splits it into a real
  shell — Overview, AHU-1, Operations, Notes — each tab owning its own poll loop, so a tab
  nobody has open isn't still hitting the gateway every 2.5s in the background.
- **The floor plan that didn't get built, and why that's a documented choice, not a gap:**
  PLAN.md's Overview page is an SVG floor plan with 4 VAV zones colored by temperature vs
  setpoint. Those zones were never built — M2 simplified AHU-1 down to one BACnet device
  with no VAV-101..104 (see M2's notes above) — so there's no per-zone temperature to
  color a floor plan with. Building a floor plan anyway would mean inventing zone data
  that doesn't correspond to anything the gateway actually polls. Overview instead
  surfaces the building-level signals that *do* exist: occupancy mode, energy now, active
  alarm count, fire panel condition, door status — the same category of information a real
  overview screen leads with, scoped to what this lab actually simulates.
- **The AHU graphic is read from live point IDs, not hand-positioned numbers:** `AhuGraphic.tsx`
  takes the same `Point[]` the gateway's `/points` endpoint returns and looks up each value
  by its point id (`ahu-1.oa_damper`, `ahu-1.fan_speed`, etc.) — so the schematic can't
  silently drift out of sync with what the gateway is actually polling the way a
  component with hardcoded mock values could.
- **Animating the fan from `fan_status`, not `fan_speed`:** a real supply fan is either
  running or it isn't — `fan_speed` just says how fast *if* running. Driving the spin
  animation off the binary `fan_status` point (rather than, say, gating on `fan_speed > 0`)
  matches how a real annunciator graphic would show it, and also means the fire interlock
  (M4) visibly stops the fan graphic the instant `fan_status` goes inactive.
- **A screenshot artifact worth knowing, not a bug:** capturing a static screenshot of the
  spinning fan while its CSS animation was still running occasionally rendered the blades
  as entirely invisible instead of motion-blurred — an animation/screenshot-timing
  interaction, not a rendering defect. Confirmed by freezing the animation
  (`animation: none`) before capturing: the blades render exactly as coded, correctly
  colored and positioned. A live browser never has this problem — only a single frozen
  frame caught at an unlucky instant can.
- **Setpoint writes narrowed to the one point already proven safe:** the write form moved
  from the old single-page Live tab to the new AHU-1 tab unchanged — still only SAT
  setpoint, the same write path validated back in M2/M3. Static pressure setpoint is
  polled and displayed but deliberately not wired to a second write form; adding it would
  be "more of the same pattern," not a new concept worth the UI surface yet.

## M8 — Alarms console, fire annunciator, access log, trends, work orders

- **Concept:** M7 gave the console a shell; M8 gives each system its own dedicated view
  instead of sharing one flat Operations page — a sortable alarms table, a real fire panel
  annunciator, an access control event log, and a trend chart. Work orders stay bundled
  with Alarms (a documented simplification, not a missing page — see below).
- **A second event log, built the same way as the first:** M6 never gave the fire panel an
  event history the way access control's `access.py` always had one. Adding
  `Panel.events: list[PanelEvent]` and appending from `trigger`/`clear_field`/
  `acknowledge`/`silence`/`reset` is the exact same pattern as `AccessControlSystem.events` —
  recognizing "this is the second instance of a pattern" (same lesson M5's notes already
  drew about the demo-proxy endpoints) meant copying a shape already proven correct rather
  than inventing a new one.
- **Making the pure functions testable meant threading `now` through, not reading the
  clock internally:** `trigger()`/`acknowledge()`/`silence()`/`reset()` used to have no time
  parameter at all — nothing needed one before events existed. Adding an event log forced
  the same choice `access.py` made in M5 (`badge(..., now: datetime)`): pass the clock in
  explicitly rather than call `datetime.now()` inside pure logic, so tests can assert exact
  timestamps and event ordering without mocking time.
- **A real bug caught by Playwright, not by any unit test:** the gateway's
  `GET /history/{point_id}` returns each sample as `{"value": ..., "timestamp": ...}` (see
  `db.py`), but the console's `HistorySample` type and `LineChart.tsx` were written against
  a guessed field name, `recorded_at`. Every Python test and every console unit test passed
  — none of them exercise the actual JSON shape crossing the wire — and the chart rendered
  as a flat `NaN` path (SVG attribute errors in the browser console, `MNaN,200 LNaN,200…`).
  Only opening the Trends tab in a real browser and reading the console surfaced it. Fixed
  by renaming the field to match the gateway's actual response, confirmed by re-reading
  `gateway/app/db.py` directly rather than re-guessing. A reminder that typing a fetch
  response doesn't verify it — only exercising the real endpoint does.
- **Acknowledged/silenced exposed as a dedicated endpoint, not threaded through points:**
  the point model (`{id, device, value, units, status}`) represents sensor/measured state;
  "has an operator acknowledged this panel" is panel UI state, not a point. Rather than
  force two booleans into that shape, `GET /fire-panel/panel` proxies the sim's full
  `/panel` response directly — a narrow, deliberate exception to "everything is a point,"
  made explicit in the endpoint's own comment rather than left implicit.
- **The floor-plan trend chart is hand-rolled SVG, not a charting library:** PLAN.md
  suggests Recharts. A single-series line chart — one path, a filled area, min/max labels,
  an emphasized last point — is a few dozen lines of SVG with no new dependency, no new
  bundle weight, and no library API to learn before trusting it. Reaching for a charting
  library would make sense once there's a real need for multi-series overlays, zoom, or
  legends; nothing here needs that yet.
- **Work orders stay inside the Alarms tab, not a separate page:** PLAN.md lists Work
  Orders as its own console page with "list + detail." The list view already exists
  (`WorkOrdersPanel`) and a work order's only real action (change status) is one dropdown —
  there's no detail worth a dedicated page yet, and work orders are created *from* alarms
  often enough that keeping them on the same tab keeps that cause-and-effect visible
  without a tab switch.

## M9 — Network page + network design doc

- **Concept:** every other milestone simulates a real system; this one documents one that
  was never going to be simulated — the lab runs on a single flat Docker bridge (`bas_net`)
  on purpose (see M0's notes), but a real building's BAS/security/fire/IT segmentation is
  exactly the kind of Network+ knowledge this project exists to showcase. `network-design.md`
  was filled in with concrete subnets, ports, and firewall rules rather than left as the
  TODO stub M0 created, and the console's new Network tab renders it directly.
- **Filling in the TODOs instead of leaving them for later:** PLAN.md §11 originally
  suggested leaving the VLAN table as a draft. By M9 every other doc in the project had
  already been written out in full rather than left as a stub, so a half-finished network
  doc would have been the one inconsistent page in the repo — filled in with realistic,
  clearly-labeled values instead, the same way every prior milestone's docs were.
- **Why fire alarm gets full isolation and BAS/Security only get "restricted":** BAS and
  Security both need one narrow, specific path out (to the gateway, to the NVR) — a real
  rule a firewall can express as "this VLAN, this one destination, these ports." Fire alarm
  monitoring in a real building is often a dedicated circuit or phone line to a central
  monitoring station, not a path *through* the building's own data network at all — so
  "isolated" here isn't a stricter version of "restricted," it's a different kind of
  boundary, and the diagram deliberately draws it with a different line style.
- **The diagram is hand-rolled SVG, same decision as the Trends chart:** PLAN.md suggests
  Mermaid, and `network-design.md` itself keeps a Mermaid block for anyone reading the
  markdown directly. The console's own rendering is a dependency-free SVG component instead
  (`NetworkDiagram.tsx`) — consistent with `LineChart.tsx`'s M8 reasoning: a static diagram
  with five boxes and a few lines doesn't justify pulling in a diagramming library just to
  render it inside an already-running React app.

## M10 — README polish, demo video, final write-up

- **Concept:** the last milestone doesn't add a feature — it makes the nine milestones
  before it legible to someone who didn't watch them get built. A portfolio project that
  works but can't be understood in two minutes by a hiring manager scrolling a repo hasn't
  finished its job.
- **Screenshots taken from a live, state-manipulated run, not a cold default:** every
  screenshot in the README was captured after actually triggering the condition it shows —
  the Fire Panel shot has a real zone in ALARM (triggered via the same demo endpoint a
  user would click), the AHU-1 shot shows the fan genuinely stopped by the interlock in
  response to that alarm, and the Trends shot is a real kW series accumulated over the
  run, not a static mock. A screenshot of an idle system proves the UI renders; a
  screenshot of a triggered interlock proves the system does what the README claims.
- **The demo script is a shot list, not a script to read:** early draft tried writing
  word-for-word narration. Rewritten as beats (what's on screen, one sentence of context)
  because a real screen recording needs room to react to what's actually happening — the
  PI loop's SAT drift, the poll interval's 2.5s lag — not force a fixed line length onto a
  live system.
- **The resume bullets lead with protocol/interlock/control-loop work, not the React
  console:** Daniel's resume already has 7 years of React/React Native. The bullets that
  matter here are the ones that wouldn't be true without the BAS-specific work — BACnet's
  priority array, a real fan-shutdown sequence, a PI loop debugged against two distinct
  failure modes (integral windup, a bang-bang limit cycle) found only by running the
  simulation, not by reading the code.

## Post-M10 — backend tactical refactor pass

A `dx-refactor-scan` across the whole repo surfaced 14 tactical and 9 strategic findings.
This batch covers the backend/Python half of the tactical tier (the console/TypeScript
half is a separate pass):

- **Normalized point shape unified behind `state.set_point()`/`fault_point()`/
  `fault_device()`:** the 6-key point literal used to be hand-written twice per poller
  (ok path + fault path) across all 4 pollers — 11 call sites total. More than
  de-duplication: the fault paths had quietly diverged. `fire_panel.py`'s fault branch
  nulled only `fire-panel.condition`, leaving every zone point and the interlock status
  showing a stale value tagged `status: "ok"` straight through a panel outage;
  `access_control.py`'s did the same for `last_event` alone, leaving `door1..3` stale.
  Verified live: stopping the access-control container now correctly faults all 4 of its
  points together (confirmed via `docker compose stop access-control` + `GET /points`),
  where before only `last_event` would have flipped.
- **The alarm engine's door scan was a hardcoded `(1, 2, 3)`:** now scans `points` for
  the `access-control.door` prefix, matching what `access_control.py`'s own poller
  already does with no fixed count. A 4th door would previously have raised no alarm at
  all, silently. Added a regression test (`test_forced_door_beyond_the_default_three_still_raises_an_alarm`).
- **Occupancy mode collapsed from three independent declarations to one:**
  `sims/bacnet_devices/main.py` used to declare `OCCUPANCY_STATE_TEXT` (a list) and
  `MODE_TO_STATE_INDEX` (a dict) separately, linked only by both authors remembering to
  keep the integers in the same order; `gateway/app/bacnet_ahu.py` kept a third,
  independent copy of the labels. The sim side is now one ordered `OCCUPANCY_MODES` list
  deriving both; the gateway's copy is the one that remains (reading `stateText` live off
  the BACnet object would remove it entirely, at the cost of an extra `ReadProperty` per
  poll — not worth it for one AHU), now with a comment naming it as the one hand-synced
  copy instead of implying there's an enforced link that doesn't exist.
- **`AHU_POINTS` was re-spelling two BACnet objects that already had named constants**
  (`AO_OA_DAMPER`, `BO_FAN_COMMAND`) as inline magic tuples a few lines below their
  declaration — now uses the constants, so the interlock's write target and the poller's
  read target can't silently desync.
- **The fan-mismatch alarm rule's real-world limits are now documented, not silently
  true — and verifying them live corrected an overclaim:** the first write of this note
  said the rule "can never fire outside its own unit tests," reasoning from
  `sims/bacnet_devices/main.py` mirroring `fan_status` from `fan_command`
  unconditionally. Actually triggering and releasing the fire interlock live disproved
  that: the rule fired and cleared for real, a few seconds apart, because `fan_command`
  resolves over BACnet the instant the interlock relinquishes priority 1 while the sim's
  own mirror line only catches up on its next poll tick. The rule can't demo a
  *sustained* fault (no fault-injection path exists for a genuinely stuck fan), but it
  isn't unreachable — a real transition proved that. Documented accurately in both the
  rule itself and `alarm-engine-notes.md` after the correction. Worth keeping as its own
  lesson: an "obviously true" claim about what a rule can and can't do is still worth
  checking against a live run before writing it down as fact.
- **`Zone`/`Door`/`Cardholder` default-copying switched from re-listing every field by
  name to `dataclasses.replace()`:** the original fix for the shared-mutable-default bug
  (M4/M5) rebuilt fresh instances by naming each field explicitly — correct today, but
  silently falls back to the dataclass's bare default for any field added later instead of
  what `DEFAULT_ZONES`/`DEFAULT_DOORS`/`DEFAULT_CARDHOLDERS` actually declare.
  `replace()` copies whatever fields exist, automatically.
- **`state.py` gained its first unit tests** (`test_state.py`) — the new helpers are pure
  dict manipulation with no I/O, extracted from what used to be inline literals in
  0%-covered poller files. Consistent with the project's whole pattern: pure logic gets
  extracted and tested, I/O stays thin.

## Post-M10 — console tactical refactor pass

The console/TypeScript half of the same `dx-refactor-scan` backlog. No automated test
infrastructure exists for React components in this project (only `lib/points.ts` has a
spec file; no jsdom, no Testing Library — see the strategic backlog's S4) so every change
here was verified the only way available: a full Docker cold start plus a real Playwright
walkthrough of every tab, including triggering a real fire alarm and a real forced door to
exercise the exact code paths that changed.

- **One `usePolledResource` hook replaces 8 hand-rolled poll loops**
  (`lib/usePolledResource.ts`): `Points`, `Overview`, `AhuPanel`, `AlarmsPanel`,
  `WorkOrdersPanel`, `TrendsPanel`, `AccessControlPanel`, and `FirePanelAnnunciator` each
  used to copy the same fetch-on-mount/`setInterval`/cancel-on-unmount shell. Confirmed
  the drift was real before touching it: two copies had already lost their own named
  `POLL_INTERVAL_MS` constant to a bare `2500` literal, and `TrendsPanel` was silently
  running on `3000` instead with no stated reason. The hook takes a fetcher, an initial
  value, and an options bag (`intervalMs`, optional `errorMessage`, optional `deps` for
  effects that need to restart on more than mount, optional `enabled` to pause without
  unmounting) and returns `{data, error, updatedAt, refresh}` — `updatedAt` is new, not a
  behavior change, just promoting a pattern `Points.tsx` already wanted
  (`lastUpdated`) into something every tab gets for free.
- **Two components combine what used to be a `Promise.all` of two independent fetches
  into one fetcher function** (`Overview`, `AccessControlPanel`, `FirePanelAnnunciator`)
  so the hook still sees one request shape per tab — same failure semantics as before
  (either fetch rejecting fails the whole combined fetch), not a behavior change.
- **`AhuPanel`'s SAT setpoint field now seeds from the live polled value, derived at
  render, instead of a hardcoded `'22.0'`:** submitting the form unedited used to silently
  revert the real device's setpoint regardless of what it actually was. First attempt
  used a `setState` inside a `useEffect` to sync the field — oxlint's
  `react(set-state-in-effect)` rule caught it immediately, and rightly: the live value is
  derivable from props/state already in scope, so there's nothing to synchronize via an
  effect. Rewritten to compute the displayed value directly during render
  (`setpointOverride ?? liveValue`), with the override cleared back to `null` on a
  successful write so the field keeps tracking the live point afterward.
- **`AccessControlControls` stopped re-fetching the cardholder list its parent already
  polls:** now takes `cardholders` as a prop. The "pick a default selection once the list
  arrives" logic hit the same `set-state-in-effect` lint rule as the setpoint field above
  and was rewritten the same way — `selectedId ?? cardholders[0]?.id ?? null` computed at
  render, no effect needed at all. `fetchCardholders()` in `api.ts` is now dead and was
  deleted.
- **One shared `toneStyle()` helper** (`lib/points.ts`) **replaces the riskiest of five
  independent status→color maps:** `AccessControlPanel`'s `DOOR_STYLE`/`RESULT_STYLE` were
  typed `Record<string, …>` and indexed unguarded — an unrecognized backend value would
  have read `.bg` off `undefined` and thrown mid-render, a real crash risk with zero test
  coverage to catch it. Each component keeps its own small, locally-typed
  `Record<RealUnion, Tone>` (what "FORCED" or "ALARM" means is still domain-specific);
  `toneStyle()` is just the one place a `Tone` becomes real CSS values, with an explicit
  `'neutral'` fallback replacing the silent crash. `FirePanelAnnunciator`'s own
  `CONDITION_STYLE` was left alone — it was already typed against the real condition
  union and therefore already safe, so migrating it would have been consistency for its
  own sake rather than fixing anything.
- **`FirePanelAnnunciator`'s `interlockActive` is now derived from `panel.any_alarm` at
  render instead of mirrored into its own state via the poll effect** — a partial poll
  failure (panel fetch succeeds, events fetch rejects, inside the same combined fetcher)
  used to leave the interlock tile frozen on the previous cycle's value instead of
  reflecting the panel that had just loaded successfully.
- **`ArchitectureDiagram`'s dead `LIVE` set removed:** it named 6 services but the 4 boxes
  it actually gated were always all of them, so every live/not-live branch had exactly one
  reachable arm — confirmed by reading the file, not assumed. The comment telling the next
  developer to "update the live set as each milestone ships" was itself stale advice for
  dead code. Deleted; the diagram renders identically since the "live" branch was the only
  one ever taken.
- **A documentation overclaim, caught by actually running the fix:** the first pass at
  documenting the fan-mismatch alarm rule (gateway/alarms.py, see the backend batch above)
  said it "can never fire outside its own unit tests." Live-verifying this console batch —
  triggering the fire alarm interlock, then releasing it — fired that exact alarm for
  real: `fan_command` resolves over BACnet the instant the interlock relinquishes priority
  1, while the sim's own `fan_status` mirror line only catches up on its next poll tick, a
  genuine if momentary disagreement. Corrected the claim in both `alarms.py`'s comment and
  `alarm-engine-notes.md` rather than leaving a confident-but-wrong statement in the repo.
  The lesson generalizes past this one rule: an "obviously true" claim about what code can
  or can't do is worth checking against a live run, not just reasoning from reading it.

## Post-M10 — strategic backlog, issue #19: Ahu1Plant moved into control.py

The cheapest item in the strategic backlog (filed as GitHub issues #14-#22 alongside the
tactical pass). `Ahu1Plant` — the class holding sequence-of-operation state across ticks —
lived in `sims/bacnet_devices/main.py`, outside the pure/tested module, despite its own
docstring claiming "all the actual decisions are the pure functions in control.py." That
wasn't true of `step()`'s own branching (which PI loop resets when the fan isn't running,
how the mixed-air/coil-effect/thermal-lag chain composes) — exactly the kind of logic a
sequence-of-operation bug hides in, and it was previously covered by nothing.

- **Injected `time_accel_x` and `rng` instead of reading them from `main.py`'s
  module-level constants:** the class used to reach out to `TIME_ACCEL_X` and the bare
  `random` module directly, which is exactly why it couldn't be unit-tested before —
  nothing could run a fast, deterministic sim day in a test. Now both are constructor
  parameters with the same defaults, so `main.py`'s construction call
  (`Ahu1Plant(time_accel_x=TIME_ACCEL_X, sim_start_hour=SIM_START_HOUR)`) is unchanged in
  behavior and `test_control.py` can pass `rng=random.Random(42)` for determinism and an
  extreme `time_accel_x` to compress a real day into 10 ticks.
- **`main.py` dropped from ~343 to ~287 lines and lost every control-logic import** — it's
  now genuinely just BACnet object wiring and the asyncio loop, matching what its own
  docstring already claimed about the file's job.
- **Coverage moved from "0% on the one file with real decision logic in it" to 100% on
  `control.py`** — `sims/bacnet_devices/tests/test_control.py` already existed at 99%
  coverage before this, so this was the cheapest item in the backlog specifically because
  the test harness didn't need to be built, just extended. 4 new tests: warmup-at-startup,
  fan-stop-resets-both-PID-integrals, the injected-not-hardcoded accel factor, and
  deterministic noise given a seeded RNG.
- **Verified live, not just via the test suite:** cold-rebuilt `bacnet-devices` + `gateway`
  in Docker and confirmed `GET /points` shows AHU-1 converging toward its SAT setpoint with
  the OA damper modulating exactly as before the move — the refactor changed where the
  code lives, not what it does.

## Post-M10 — strategic backlog, issue #18: declarative proxy binding

`gateway/app/main.py` has 13 routes that are pure pass-throughs to the fire panel or
access control sim, all already funneling through one `_proxy()` helper — but the
service name and base URL (`"Fire panel", fire_panel.FIRE_PANEL_URL`,
`"Access control", access_control.ACCESS_CONTROL_URL`) were retyped as positional
arguments at every one of those 13 call sites.

- **`functools.partial` binds each service once** (`fire_panel_proxy`,
  `access_control_proxy`), not a generic row-based route table. The issue's own framing
  called for a "declarative table," but the 13 routes have genuinely different
  signatures — path params, a request body needing a field rename (`TriggerZoneBody` →
  `{"condition": ...}`), query params, one route proxying to a *different* path than its
  own name suggests (`GET /access-control/cardholders` → sim's `/state`) — so a fully
  generic table would need to re-invent per-route body/path/query handling FastAPI
  already gives every individually-declared route for free. `partial` closes the actual
  duplication (the service/URL pair) without losing that.
- **Each route stays its own `@app.get`/`@app.post` declaration, on purpose:** the
  explicit list is functionally an allowlist — only these specific sim operations are
  reachable from the console — and collapsing it into a generic `{path:path}` forwarder
  would quietly turn that allowlist into a pass-everything proxy. The decision recorded
  in the GitHub issue (declarative binding yes, catch-all forwarder no) is the one that
  shipped.
- **Verified live:** cold-rebuilt `gateway` + `fire-panel` + `access-control`, then
  curled all 13 routes individually, including the one with a mismatched path
  (`/access-control/cardholders` → `/state`) and a deliberate 404 to confirm the error
  `detail` still passes through unchanged.

## Post-M10 — strategic backlog, issue #14: the point shape becomes a real type

The deepest of the strategic items tackled so far. `gateway/app/state.py` used to declare
`points: dict[str, dict]` — a shape enforced only by convention (M6's tactical pass, #12,
closed the *writing* side with `set_point()`/`fault_point()`/`fault_device()`, but every
*consumer* still read it back out as an untyped dict).

- **New `gateway/app/points.py`:** a `Point` dataclass (`id`, `device`, `name`, `value`,
  `units`, `status`), plus `publish()`/`fault()`/`fault_device()` (moved here from
  `state.py`) and a new `numeric_points()` — the predicate `supervisor.py` used to
  inline as a bare `isinstance(p.get("value"), (int, float))` is now a named, tested
  function in the one module that owns the point shape. Kept dependency-free and pure,
  same as `alarms.py`/`work_orders.py`.
- **`state.py` keeps the exact same `set_point()`/`fault_point()`/`fault_device()` names
  and call signatures**, now as thin wrappers delegating to `points.py` — every poller
  (`modbus_meter.py`, `bacnet_ahu.py`, `fire_panel.py`, `access_control.py`) is
  byte-for-byte unchanged. Only the *consumers* (`alarms.py`, `supervisor.py`, `main.py`)
  needed to switch from dict-subscript (`point["value"]`) to attribute access
  (`point.value`) — exactly the blast-radius tradeoff the issue called for.
- **The `'stale'` decision, made explicit rather than left implicit:** the issue flagged
  that nothing on the backend has ever emitted `'stale'`, and asked whether it's a real
  state worth building (age-tracking in the supervisor) or dead surface to delete.
  Decided: delete. Implementing staleness detection would be new behavior, not a
  refactor — scope-creeping a "model the existing shape" issue into "add a feature" is
  exactly the kind of drift `dx-refactor`'s own discipline warns against. Removed the
  union member from `console/src/lib/api.ts`'s `Point` interface and its orphaned chip
  style in `Points.tsx`. If staleness detection is ever wanted, it's a new, separate,
  product-scoped issue — not smuggled into this one.
- **`GET /points`'s JSON shape is verified byte-identical**, not just assumed: FastAPI
  serializes the `Point` dataclass the same way it serialized the old dict (confirmed in
  this project before, re-confirmed here) — same 6 keys, same order, verified against a
  live cold-started gateway.
- **Test suites updated to construct the real type:** `test_alarms.py`'s `point()`
  helper and `test_state.py`'s assertions now build `Point` instances instead of dict
  literals — the tests exercise the same type the production code does, not a stand-in
  that happens to look similar. A new `test_points.py` covers `publish`/`fault`/
  `fault_device`/`numeric_points` directly (5 tests); gateway suite: 24 → 29.
- **Verified live beyond the test suite:** full Docker cold start, confirmed `GET
  /points`'s shape, triggered and cleared a real fire alarm end-to-end against the new
  model, confirmed trend history still records numeric points, and loaded the console's
  Points tab in a real browser with zero console errors after removing the dead
  `'stale'` status.

## Post-M10 — strategic backlog, issue #15: one poller shell for all four devices

`modbus_meter.py`, `bacnet_ahu.py`, `fire_panel.py`, and `access_control.py` each
hand-wrote an identical `while True`/`try`/`except`/`asyncio.sleep` loop, differing only
in transport and point mapping — the exact shape whose fault-path divergence already
bit once (#12's tactical fix). Depended on #14 (the `Point` model) landing first.

- **The contract: `read(known) -> list[Point]`, not `read() -> list[Point]`.** The
  issue's own suggested signature was `read() -> list[Point]`, with the device module
  catching its own transport errors internally. That works cleanly for `modbus_meter.py`
  (one point) and `bacnet_ahu.py` (a fixed, hardcoded point list) — but `fire_panel.py`
  and `access_control.py` fault a *dynamic*, sim-reported set (zones, doors) on failure,
  previously done via `fault_device()` reading whatever the global store already had.
  Without access to that store, `read()` would have had no way to know what to fault
  without hardcoding a zone/door count — reintroducing the exact bug T4's fix (#12)
  eliminated from the alarm engine. `read()` takes a read-only snapshot of the store as
  of the start of the tick instead, so the dynamic-fault-set devices can scan it the same
  way `fault_device()` used to, while `modbus_meter.py`/`bacnet_ahu.py` simply ignore the
  argument. A deliberate, documented departure from the issue's literal suggestion in
  favor of preserving a correctness guarantee already established.
- **New `gateway/app/poller.py`:** `run_poller(name, interval_s, read, store, log)` is the
  one place the loop shape lives now. Its own `try`/`except` is a last-resort safety net
  for a bug *in* `read()` itself (asserted directly in `test_poller.py` — the loop
  survives and keeps ticking even if a device module's `read()` raises unexpectedly), not
  the normal "device unreachable" path, which every `read()` is expected to handle
  internally and turn into fault `Point`s.
- **`fire_panel.py`'s `read()` still drives the AHU-1 interlock as a side effect** — it
  does more than read. That's a known, named scope boundary: moving the interlock
  decision into `supervisor.py` is #16, which explicitly depends on this issue landing
  first. Not conflated here.
- **`state.py`'s `set_point()`/`fault_point()`/`fault_device()` wrappers are now dead
  code and removed** — every poller constructs `Point` instances and returns them
  directly; `poller.py`'s shell owns writing to the store. `state.py` shrinks back to
  just the three shared globals its own docstring always claimed it was for.
  `test_state.py` (which only tested those now-removed wrappers) is deleted; the
  underlying `publish`/`fault`/`fault_device` logic it exercised is still covered
  directly in `test_points.py`, unchanged.
- **Every poller is unit-tested against a fake transport for the first time** — these
  files were 0%-covered by design before (verified via `docker compose` + curl, not
  units). A `_FakeModbusClient`, `_FakeApp` (BACnet), and a shared `_FakeHttpClient`
  shape (fire panel, access control) stand in for the real client objects, monkeypatched
  onto each module's lazy module-level singleton. 14 new tests across the four device
  modules plus `poller.py` itself; gateway suite: 29 → 42 (console/sim suites
  untouched).
- **Verified live, the same bar as every prior backlog item:** full Docker cold start,
  confirmed all 4 devices still publish only `"ok"` points under normal operation,
  triggered a real fire alarm and confirmed the interlock still engages/releases
  correctly (fan command, OA damper, and the `ahu-1.fire_interlock` point all tracked
  correctly through the new shell), then stopped the `fire-panel` container and
  confirmed its condition, all 4 zones, and the interlock point fault together exactly
  as before — and recover cleanly on restart.

## Post-M10 — strategic backlog, issue #16: the fire interlock moves into the supervisor

The highest-subtlety item in the backlog (effort M, risk high, explicitly sequenced
last — depends on #14 and #15). `fire_panel.py` was both a poller *and* the AHU-1
interlock control strategy; `supervisor.py`'s own docstring already described exactly
that job ("read a snapshot, act on it"), but the interlock lived somewhere else.

- **Locked in today's behavior with a test before touching anything**, per the issue's
  own instruction: `test_bacnet_ahu.py` gained a `_FakeWriterApp` recording every
  `write_property()` call, asserting the exact engage sequence (fan off, then damper to
  0%, both at priority 1), the exact release sequence (both relinquished via `Null(())`,
  never a plain value), and that engaging twice in a row sends the identical write both
  times (idempotent, not edge-triggered). Ran green against the *old* code first,
  confirming the behavior these tests pin down is real before relying on them to prove
  the move didn't change it. `bacnet_ahu.py`'s `engage_fire_interlock()`/
  `release_fire_interlock()` themselves are untouched by this issue — only *who calls
  them* moved — so these tests still pass unchanged after the move, which is the actual
  proof.
- **`decide_interlock(snapshot) -> bool | None`** is the pure decision, now living in
  `supervisor.py`: `True` engages, `False` releases, `None` means the fire panel's
  condition is currently unknown (faulted or never published). Checking the panel's
  overall `condition == "ALARM"` is equivalent to the sim's own raw `any_alarm` flag the
  old code read directly — `sims/fire_panel/panel.py`'s `overall_condition()` already
  forces `condition` to `ALARM` whenever any zone is in alarm (alarm beats trouble beats
  supervisory), so the published point carries the same information.
- **A real design decision the move forced into the open: what happens when the fire
  panel goes unreachable?** The old code's BACnet write lived inside the *same*
  try/except as the `/panel` fetch, so a comms failure meant the write simply never
  happened that cycle — the interlock silently stayed wherever it was. Splitting
  decide/apply meant deciding this on purpose instead of inheriting it by accident:
  `decide_interlock()` returns `None` on an unknown condition, and the supervisor sends
  **no new BACnet command** in that case (verified live — stopping the fire-panel
  container left `ahu-1.fan_command` untouched) while still publishing
  `ahu-1.fire_interlock` as faulted (an improvement over before: the old code faulted
  that point too, but only because it happened to sit in the same except block — now
  it's an explicit, named case in `decide_interlock()`'s own contract rather than a side
  effect of where the code used to live).
- **A real, named cadence change:** the interlock decision used to run on
  `fire_panel.py`'s own 2-second poll; it now runs on `supervisor.py`'s 3-second tick.
  Slightly slower worst-case response to an alarm, in exchange for one clock driving
  every decision this gateway makes instead of each decision bringing its own timer.
  Named here rather than discovered later.
- **`fire_panel.py` lost its only non-REST dependency** — it no longer imports
  `bacnet_ahu` at all, matching its docstring's claim that it's "not a field protocol"
  more honestly than before (previously true of its *polling*, not of what it did with
  the result).
- **New `test_supervisor.py`** (9 tests): `decide_interlock()` tested directly against
  every condition value including the faulted/missing cases; `apply_interlock()` tested
  against a monkeypatched `bacnet_ahu` confirming both idempotent re-send and that
  `True`/`False` route to `engage`/`release` correctly — no BACnet stack needed, closing
  the exact gap the issue opened with ("the interlock can't be unit-tested without a
  live BACnet stack... zero tests today").
- **Verified live, the full chain:** full Docker cold start; triggered a real fire alarm
  and confirmed engage (fan → inactive, damper → 0%) through the new code path;
  cleared/reset and confirmed release; stopped the `fire-panel` container and confirmed
  the designed-on-purpose behavior — condition and the interlock both fault, but
  `fan_command` stays exactly where it was, matching `decide_interlock()`'s documented
  contract instead of guessing.
