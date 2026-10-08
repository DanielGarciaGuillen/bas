# Alarm Engine Notes

How the gateway turns raw point state into alarms, trend history, and work orders (M6).
See `gateway/app/alarms.py`, `gateway/app/work_orders.py`, `gateway/app/db.py`, and
`gateway/app/supervisor.py`.

## Lifecycle

```
active_unacked ──ack──> active_acked ──clear──> cleared
       └───────────────────clear────────────────^
```

- **`active_unacked`** — the engine raised this alarm and no operator has acknowledged it.
- **`active_acked`** — an operator called `POST /alarms/{id}/ack`. The underlying condition
  is unchanged; this only records that a human has seen it.
- **`cleared`** — the engine re-evaluated the same rule and the condition is gone, from
  either state. Ack is not a prerequisite for clear.

Each alarm `key` (e.g. `fire-panel.condition`) has at most one *active* row at a time. If
the condition re-raises after clearing, it opens a new row with a new `id` — cleared alarms
are never reused, so the alarm table is also the audit trail.

## Rules

Evaluated against one point snapshot every supervisor tick (`SUPERVISOR_INTERVAL_S`,
default 3s):

| Key | Condition | Priority |
|---|---|---|
| `fire-panel.condition` | Fire panel condition is not `normal` | 1 |
| `access-control.door.<id>` | A door is `forced` or `held_open` | 2 |
| `ahu-1.fan-mismatch` | Fan command and fan status disagree | 2 |
| `ahu-1.sat-deviation` | Measured SAT outside a 2°C deadband of setpoint, continuously, for 30s | 3 |

Lower number = higher priority, matching the convention already used for BACnet priority
arrays elsewhere in this project.

The SAT rule is the only one with a time element: a single bad sample doesn't raise it,
since AHU-1's PI loop (M3) is expected to overshoot briefly after a setpoint step. The
engine tracks a per-point "deviation since" timestamp, raises only once that's been true
continuously past the delay, and resets the timestamp the moment the point comes back
inside the deadband — so a loop that's still converging never trips it.

**The fan-mismatch rule can't demo a *sustained* fault against the live stack, but it does
fire correctly on real transitions.** `sims/bacnet_devices/main.py` mirrors `fan_status`
from `fan_command` unconditionally — no fault-injection path exists for a genuinely stuck
or failed fan — so there's no way to hold the two values apart indefinitely for a demo.
Confirmed live, though: triggering the fire interlock and then releasing it does raise and
clear this alarm for real, a few seconds apart. `fan_command` resolves back to the
schedule's value over BACnet the instant the interlock relinquishes priority 1, while the
sim's own mirror line only catches up on its next poll tick — a real, if momentary,
disagreement the gateway correctly alarms on. Demoing a *sustained* mismatch (an actually
broken fan) would need a fault-injection control on the AHU sim, matching the trigger-based
demo pattern the fire panel and access control sims already have. Not built — adding a
believable "fault injection" surface across every sim is a bigger, decision-needing piece
of work than this rule alone justifies on its own.

## Work orders

A work order (`gateway/app/work_orders.py`) is a plain record — `asset`, `problem`,
`priority`, `status` (`open → in_progress → done`), optional `notes`, and an optional
`source_alarm_id` linking it back to the alarm that prompted it, if any. Two are seeded at
startup (`seed_preventive_maintenance`) to make the Work Orders panel non-empty on first
load: a 90-day AHU-1 filter change and the fire panel's annual CAN/ULC-S536 inspection —
both preventive, not alarm-driven, which is why `source_alarm_id` is `null` on both.

Creating one from an alarm (`POST /alarms/{id}/work-order`) carries the alarm's `key` and
`message` forward as `asset`/`problem`, so the link from "why does this work order exist"
back to the alarm is never lost, even after the alarm itself clears.

## History

`gateway/app/db.py` writes every numeric point to a SQLite table (`point_history`) once
per supervisor tick, via `asyncio.to_thread` so the write never blocks the poll loop.
`GET /history/{point_id}?minutes=60&limit=2000` reads it back. This is scoped for a demo —
a few numeric points sampled every few seconds — not a production historian's retention or
compression needs.

## Console (M8)

The Alarms tab shows this list sortable by priority or newest-first, plus the work order
list underneath — the two stay on one tab rather than splitting into separate pages, since
a work order is so often created *from* an alarm that the cause-and-effect is worth keeping
visible without a tab switch. See `docs/engineering-notes.md`'s M8 section.

## What M6 does not do (and why)

PLAN.md bundles a WebSocket push channel into M6 alongside the alarm engine, history, and
work orders. That's deferred: the console already polls `/points`, `/alarms`, and
`/work-orders` every 2.5s, which is fast enough that a push channel wouldn't be visibly
different in a demo, and every other milestone's REST-polling pattern already covers the
same ground. If/when it's picked up, it's additive — a `/ws` endpoint broadcasting the same
normalized shapes the REST endpoints already return — not a rework of this engine.
