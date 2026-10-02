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

_TODO after milestone._

## M2 — BACnet AHU + VAV devices

_TODO after milestone._

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
