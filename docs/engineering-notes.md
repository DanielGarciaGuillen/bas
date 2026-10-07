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

_TODO after milestone._

## M8 — Alarms console, fire annunciator, access log, trends, work orders

_TODO after milestone._

## M9 — Network page + network design doc

_TODO after milestone._

## M10 — README polish, demo video, final write-up

_TODO after milestone._
