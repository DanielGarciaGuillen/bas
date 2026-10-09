# Access Control Notes

## Doors and cardholders

| Door | Required level |
|---|---|
| Main Entrance | 1 |
| Server Room | 2 |
| Mechanical Room | 3 |

| Cardholder | Level | Schedule | Can reach |
|---|---|---|---|
| Alice Chen (facilities manager) | 3 | always | all three doors, anytime |
| Priya Natarajan (security) | 2 | always | Main Entrance, Server Room, anytime |
| Evan Walsh (night cleaner) | 1 | always | Main Entrance only, anytime |
| Carla Diaz (IT) | 2 | business_hours | Main Entrance, Server Room, business hours only |
| Bob Singh (general staff) | 1 | business_hours | Main Entrance only, business hours only |
| Dan O'Brien (general staff) | 1 | business_hours | Main Entrance only, business hours only |

"Business hours" is Monday–Friday, 8:00–18:00, checked against the real wall-clock time —
there's no simulated/accelerated clock here the way AHU-1 has one, since access events are
triggered on demand rather than running an autonomous day/night cycle.

> **Deliberate inconsistency, documented rather than fixed (GitHub issue #21):** AHU-1
> runs on an accelerated sim day (a full 24h cycle in a few real minutes — see
> `docs/sequences-of-operation.md`), while access control schedules check the real
> wall clock. The two subsystems can disagree about "what time it is" — e.g. the AHU
> graphic shows "Occupied" while a `business_hours` cardholder is denied at 9pm on a
> real Saturday. Each choice is independently correct (AHU-1 needs an accelerated clock
> to make an autonomous day/night cycle demoable at all; access control has no
> autonomous cycle to accelerate — every event is triggered on demand), so unifying them
> would mean inventing a shared "building time" concept neither subsystem actually
> needs on its own. Left as two independently-reasonable simplifications rather than
> building a shared clock to reconcile them. Worth knowing before a live demo: badge
> events and the AHU's occupancy mode won't necessarily agree outside real business
> hours, and that's expected, not a bug.

## Events

Every badge attempt, forced door, and held-open door produces an event with a plain-English
reason:

| Result | Meaning |
|---|---|
| `granted` | Sufficient access level, within schedule |
| `denied_level` | Cardholder's access level is below the door's requirement |
| `denied_schedule` | Right level, but outside the cardholder's permitted hours |
| `forced` | Door opened without a valid badge |
| `held_open` | Door held open past the 30-second threshold |

`forced` and `held_open` put the door into an alarm state (`any_alarm()`), which the
gateway surfaces as a point but — unlike the fire panel — doesn't yet act on. Wiring
forced/held-open doors into an actual alarm lifecycle (acknowledge, priority, a work
order) is M6's job, not this module's.

## Implementation notes

- Simulator: `sims/access_control/main.py` (FastAPI wiring) + `access.py` (the pure,
  unit-tested access-decision logic — same split as the fire panel's `panel.py`).
- Same deliberate protocol boundary as the fire panel: REST, not BACnet/Modbus. See
  `docs/fire-alarm-notes.md` for why that boundary exists.
- `AccessControlSystem`'s doors/cardholders are built fresh per instance in
  `__post_init__` rather than reused from the module-level `DEFAULT_DOORS`/
  `DEFAULT_CARDHOLDERS` lists — the same shared-mutable-default bug class caught in
  `sims/fire_panel/panel.py` during M4, applied here before it had the chance to bite.
- Gateway client: `gateway/app/access_control.py` polls `/state` and the latest `/events`
  entry; demo-trigger proxy endpoints live in `gateway/app/main.py` under
  `/access-control/...`, reusing the same generic `_proxy()` helper the fire panel uses.
