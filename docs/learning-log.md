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
