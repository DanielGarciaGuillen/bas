# Learning Log

Notes for Daniel: the concept behind each milestone, why it matters in real buildings, and
one likely interview question with a short answer. Write these in your own words as you go.

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
- **Interview question:** *"Why would a building have both field-level protocols like
  BACnet/Modbus and a web-based front end?"*
  **Short answer:** Field protocols are what the controllers natively speak (lightweight,
  deterministic, built for control networks); the web front end is for human operators and
  needs a translation layer (the gateway/supervisor) that normalizes different protocols
  into one point model and exposes them over HTTP/WebSocket.

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
- **Interview question:** *"How would a gateway know that register 0 on this particular
  meter means kW and not, say, voltage?"*
  **Short answer:** It doesn't, unless told — the register map is out-of-band knowledge
  (a spec sheet, or in this project, `docs/modbus-register-map.md`) that the gateway's
  polling code is written against. Unlike BACnet, Modbus has no self-describing object
  model.

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
- **Interview question:** *"What's the practical difference between how BACnet and Modbus
  expose a point?"*
  **Short answer:** Modbus is anonymous numbered registers — the meaning lives entirely in
  out-of-band documentation both ends must agree on in advance. BACnet objects carry their
  own type, name, units, and status as part of the protocol itself, which is also why
  BACnet supports device and object discovery (Who-Is/I-Am) that Modbus has no equivalent
  for.

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
- **Interview question:** *"Why would a BAS web client never talk BACnet directly from the
  browser?"*
  **Short answer:** BACnet/IP is UDP-broadcast-heavy and has no browser-native transport
  (no `fetch`-over-BACnet); more fundamentally, the supervisory layer exists specifically
  so protocol-speaking and presentation are separate concerns — the browser should only
  ever need HTTP/WebSocket to one normalized API.

## Console hardening — adopting real project hygiene, and an in-app Learn tab

Re-architected the console to match the conventions of a production codebase (a personal
one, `ott-next`) rather than a quick prototype, and folded the field-course content
directly into the app as a **Learn** tab (replacing a standalone course page kept outside
the repo).

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
- **Why fold the course into the app:** a separate course page is one more thing to keep in
  sync by hand every milestone. A `MODULES` array of React components next to the code it
  documents can't drift the same way a copy-pasted artifact can — and it ships with the
  portfolio piece itself instead of living beside it.
- **Testable extraction:** pulled `protocolFor`/`formatValue` out of the table component
  into `lib/points.ts` purely so they'd have something to unit-test — the same "extract the
  pure decode step" pattern used for the gateway's Modbus/BACnet polling.

## M3 — Thermal model + sequences of operation

_TODO after milestone._

## M4 — Fire alarm panel + interlock

_TODO after milestone._

## M5 — Access control sim

_TODO after milestone._

## M6 — Alarm engine, history, work orders, WebSocket

_TODO after milestone._

## M7 — Console shell, overview, AHU graphic

_TODO after milestone._

## M8 — Alarms console, fire annunciator, access log, trends, work orders

_TODO after milestone._

## M9 — Network page + network design doc

_TODO after milestone._

## M10 — README polish, demo video, final write-up

_TODO after milestone._
