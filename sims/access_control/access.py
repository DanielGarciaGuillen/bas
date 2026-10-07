"""Pure access control logic — the model underneath main.py's REST wiring.

Kept separate and dependency-free (no FastAPI here) so badge-in/force/hold-open rules are
unit-testable on their own. See docs/access-control-notes.md for the plain-English version.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time
from typing import Literal

DoorState = Literal["normal", "forced", "held_open"]
EventResult = Literal["granted", "denied_level", "denied_schedule", "forced", "held_open"]
Schedule = Literal["always", "business_hours"]


@dataclass
class Door:
    id: int
    name: str
    required_level: int
    state: DoorState = "normal"


@dataclass
class Cardholder:
    id: int
    name: str
    access_level: int
    schedule: Schedule = "always"


@dataclass
class AccessEvent:
    door_id: int
    cardholder_id: int | None
    result: EventResult
    reason: str
    timestamp: datetime


# Three doors per PLAN §4.4, each requiring a higher access level than the last.
DEFAULT_DOORS = [
    Door(id=1, name="Main Entrance", required_level=1),
    Door(id=2, name="Server Room", required_level=2),
    Door(id=3, name="Mechanical Room", required_level=3),
]

# Six cardholders spanning every (level, schedule) combination worth demoing: a facilities
# manager with full 24/7 access, day-shift staff, IT with server access during the day,
# 24/7 security with server access, and a night cleaner who can only ever get past the
# front door.
DEFAULT_CARDHOLDERS = [
    Cardholder(id=1, name="Alice Chen", access_level=3, schedule="always"),
    Cardholder(id=2, name="Bob Singh", access_level=1, schedule="business_hours"),
    Cardholder(id=3, name="Carla Diaz", access_level=2, schedule="business_hours"),
    Cardholder(id=4, name="Dan O'Brien", access_level=1, schedule="business_hours"),
    Cardholder(id=5, name="Priya Natarajan", access_level=2, schedule="always"),
    Cardholder(id=6, name="Evan Walsh", access_level=1, schedule="always"),
]


@dataclass
class AccessControlSystem:
    doors: dict[int, Door] = field(default_factory=dict)
    cardholders: dict[int, Cardholder] = field(default_factory=dict)
    events: list[AccessEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Fresh instances per system — same bug class as sims/fire_panel/panel.py's
        # Panel: reusing DEFAULT_DOORS/DEFAULT_CARDHOLDERS objects directly would share
        # them by reference across every AccessControlSystem ever constructed.
        # replace(d)/replace(c) copy every field automatically — unlike re-listing each
        # field by name, adding a field to Door/Cardholder can't silently fall back to
        # the dataclass's bare default here instead of what DEFAULT_DOORS/
        # DEFAULT_CARDHOLDERS actually declare.
        if not self.doors:
            self.doors = {d.id: replace(d) for d in DEFAULT_DOORS}
        if not self.cardholders:
            self.cardholders = {c.id: replace(c) for c in DEFAULT_CARDHOLDERS}


BUSINESS_START = time(8, 0)
BUSINESS_END = time(18, 0)


def within_schedule(cardholder: Cardholder, now: datetime) -> bool:
    if cardholder.schedule == "always":
        return True
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    return BUSINESS_START <= now.time() < BUSINESS_END


def badge(
    system: AccessControlSystem, door_id: int, cardholder_id: int, now: datetime
) -> AccessEvent:
    door = system.doors[door_id]
    cardholder = system.cardholders[cardholder_id]

    if cardholder.access_level < door.required_level:
        event = AccessEvent(
            door_id,
            cardholder_id,
            "denied_level",
            f"{cardholder.name} (level {cardholder.access_level}) lacks access to "
            f"{door.name} (requires level {door.required_level})",
            now,
        )
    elif not within_schedule(cardholder, now):
        event = AccessEvent(
            door_id,
            cardholder_id,
            "denied_schedule",
            f"{cardholder.name} is outside their permitted schedule ({cardholder.schedule})",
            now,
        )
    else:
        door.state = "normal"
        event = AccessEvent(
            door_id, cardholder_id, "granted", f"{cardholder.name} granted at {door.name}", now
        )
    system.events.append(event)
    return event


def force_open(system: AccessControlSystem, door_id: int, now: datetime) -> AccessEvent:
    door = system.doors[door_id]
    door.state = "forced"
    event = AccessEvent(
        door_id, None, "forced", f"{door.name} forced open without a valid badge", now
    )
    system.events.append(event)
    return event


def hold_open(system: AccessControlSystem, door_id: int, now: datetime) -> AccessEvent:
    door = system.doors[door_id]
    door.state = "held_open"
    event = AccessEvent(door_id, None, "held_open", f"{door.name} held open past 30s", now)
    system.events.append(event)
    return event


def clear_door(system: AccessControlSystem, door_id: int) -> Door:
    door = system.doors[door_id]
    door.state = "normal"
    return door


def any_alarm(system: AccessControlSystem) -> bool:
    return any(d.state in ("forced", "held_open") for d in system.doors.values())
