"""Pure fire alarm panel logic — the FSM underneath main.py's REST wiring.

Kept separate and dependency-free (no FastAPI here) so the panel's acknowledge/silence/
reset rules are unit-testable on their own. See docs/fire-alarm-notes.md for the
plain-English version, and the disclaimer there about real fire alarm systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

ZoneCondition = Literal["normal", "alarm", "trouble", "supervisory"]
PanelEventKind = Literal["trigger", "clear", "acknowledge", "silence", "reset"]


@dataclass
class Zone:
    id: int
    name: str
    condition: ZoneCondition = "normal"
    # Whether the *field device* itself has returned to normal (smoke cleared, pull
    # station restored). A panel can only reset once every zone's field condition has
    # cleared — matching real practice, where you can't reset a panel while a detector
    # is still in alarm.
    field_cleared: bool = True


@dataclass
class PanelEvent:
    kind: PanelEventKind
    zone_id: int | None
    detail: str
    timestamp: datetime


@dataclass
class Panel:
    zones: dict[int, Zone] = field(default_factory=dict)
    acknowledged: bool = False
    silenced: bool = False
    events: list[PanelEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.zones:
            # Fresh Zone instances per Panel — DEFAULT_ZONES's own objects are shared
            # at module scope, so reusing them directly would let one Panel's mutations
            # (triggering a zone, clearing it) leak into every other Panel ever
            # constructed. Caught by the test suite itself: tests passed in isolation
            # but failed once run together in one session.
            # replace(z) copies every field automatically — unlike re-listing each field
            # by name, adding a field to Zone can't silently fall back to the dataclass's
            # bare default here instead of what DEFAULT_ZONES actually declares.
            self.zones = {z.id: replace(z) for z in DEFAULT_ZONES}


# One zone per PLAN §4.3's device list; zone 4 groups the duct detector and flow switch
# the way a real conventional panel wires multiple devices onto one zone circuit.
DEFAULT_ZONES = [
    Zone(id=1, name="Smoke Detector — Lobby"),
    Zone(id=2, name="Smoke Detector — Office Area"),
    Zone(id=3, name="Pull Station — Main Entrance"),
    Zone(id=4, name="Duct Smoke Detector (AHU-1) / Sprinkler Flow Switch"),
]


def overall_condition(panel: Panel) -> ZoneCondition:
    """Alarm beats trouble beats supervisory beats normal, same as a real panel's
    annunciator priority — an alarm is never hidden behind a lesser condition."""
    conditions = {z.condition for z in panel.zones.values()}
    for priority in ("alarm", "trouble", "supervisory"):
        if priority in conditions:
            return priority  # type: ignore[return-value]
    return "normal"


def any_alarm(panel: Panel) -> bool:
    return any(z.condition == "alarm" for z in panel.zones.values())


def trigger(panel: Panel, zone_id: int, condition: ZoneCondition, now: datetime) -> Zone:
    if condition == "normal":
        raise ValueError("use clear_field()/reset() to return a zone to normal")
    zone = panel.zones[zone_id]
    zone.condition = condition
    zone.field_cleared = False
    # a new condition demands fresh attention — don't let it hide behind an old ack
    panel.acknowledged = False
    panel.silenced = False
    panel.events.append(PanelEvent("trigger", zone_id, f"{zone.name}: {condition}", now))
    return zone


def clear_field(panel: Panel, zone_id: int, now: datetime) -> Zone:
    """The field device itself has returned to normal (smoke cleared, station
    restored). The panel still shows the condition until an operator resets it —
    clearing the field and resetting the panel are deliberately separate actions."""
    zone = panel.zones[zone_id]
    zone.field_cleared = True
    panel.events.append(PanelEvent("clear", zone_id, f"{zone.name}: field cleared", now))
    return zone


def acknowledge(panel: Panel, now: datetime) -> None:
    panel.acknowledged = True
    panel.events.append(PanelEvent("acknowledge", None, "Panel acknowledged", now))


def silence(panel: Panel, now: datetime) -> None:
    panel.silenced = True
    panel.events.append(PanelEvent("silence", None, "Panel silenced", now))


class ResetBlocked(Exception):
    def __init__(self, blocking_zones: list[Zone]) -> None:
        self.blocking_zones = blocking_zones
        names = ", ".join(z.name for z in blocking_zones)
        super().__init__(f"cannot reset while still active: {names}")


def reset(panel: Panel, now: datetime) -> None:
    blocking = [z for z in panel.zones.values() if z.condition != "normal" and not z.field_cleared]
    if blocking:
        raise ResetBlocked(blocking)
    for zone in panel.zones.values():
        zone.condition = "normal"
        zone.field_cleared = True
    panel.acknowledged = False
    panel.silenced = False
    panel.events.append(PanelEvent("reset", None, "Panel reset", now))
