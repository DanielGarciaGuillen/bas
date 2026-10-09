"""The alarm engine — pure, unit-tested logic evaluating the normalized point model for
conditions worth raising an alarm over. Deliberately lives in the gateway, not any one
sim: these rules cross point sources (comparing AHU-1's own command against its own
status, for instance) in a way no single sim's own logic should need to know about.

Lifecycle per PLAN.md §5.5: ACTIVE_UNACKED -> ACTIVE_ACKED -> CLEARED. Clearing happens
automatically when the underlying condition resolves (same as a real panel); acking is
the only thing an operator does by hand. An alarm can also go ACTIVE_UNACKED -> CLEARED
directly if nobody acks it before the condition resolves — both paths are real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .points import PointStore

AlarmState = Literal["active_unacked", "active_acked", "cleared"]

# A deviation has to persist this long, past this deadband, before it's worth an alarm —
# the classic high/low-limit-with-deadband-and-delay shape from PLAN.md §5.5, rather than
# alarming on every momentary blip while the PI loop is still settling.
SAT_DEADBAND_C = 2.0
SAT_DELAY_S = 30.0


@dataclass
class Alarm:
    id: int
    key: str
    message: str
    priority: int  # 1 (highest) .. 4 (lowest)
    state: AlarmState
    created_at: datetime
    updated_at: datetime
    acked_at: datetime | None = None
    cleared_at: datetime | None = None


class AlarmUnackable(Exception):
    def __init__(self, alarm: Alarm) -> None:
        self.alarm = alarm
        super().__init__(f"alarm {alarm.id} is already {alarm.state}, not active_unacked")


class AlarmEngine:
    def __init__(self) -> None:
        self._alarms: list[Alarm] = []
        self._active_by_key: dict[str, int] = {}
        self._deviation_since: dict[str, datetime] = {}
        self._next_id = 1

    def all_alarms(self) -> list[Alarm]:
        return list(self._alarms)

    def active_alarms(self) -> list[Alarm]:
        return [a for a in self._alarms if a.state != "cleared"]

    def get(self, alarm_id: int) -> Alarm | None:
        return next((a for a in self._alarms if a.id == alarm_id), None)

    def ack(self, alarm_id: int, now: datetime) -> Alarm:
        alarm = self.get(alarm_id)
        if alarm is None:
            raise KeyError(f"no such alarm: {alarm_id}")
        if alarm.state != "active_unacked":
            raise AlarmUnackable(alarm)
        alarm.state = "active_acked"
        alarm.acked_at = now
        alarm.updated_at = now
        return alarm

    def _raise(self, key: str, message: str, priority: int, now: datetime) -> None:
        """Open a new alarm for `key`, or leave the existing active one alone if it's
        already open — re-raising on every tick would spam a new alarm every poll."""
        if key in self._active_by_key:
            return
        alarm = Alarm(
            id=self._next_id,
            key=key,
            message=message,
            priority=priority,
            state="active_unacked",
            created_at=now,
            updated_at=now,
        )
        self._next_id += 1
        self._alarms.append(alarm)
        self._active_by_key[key] = alarm.id

    def _clear(self, key: str, now: datetime) -> None:
        alarm_id = self._active_by_key.pop(key, None)
        if alarm_id is None:
            return
        alarm = self.get(alarm_id)
        if alarm is not None:
            alarm.state = "cleared"
            alarm.cleared_at = now
            alarm.updated_at = now

    def evaluate(self, points: PointStore, now: datetime) -> None:
        self._evaluate_fire(points, now)
        self._evaluate_doors(points, now)
        self._evaluate_fan_mismatch(points, now)
        self._evaluate_sat_deviation(points, now)

    def _evaluate_fire(self, points: PointStore, now: datetime) -> None:
        key = "fire-panel.condition"
        point = points.get(key)
        if point is None or point.value is None:
            return
        if point.value != "NORMAL":
            self._raise(key, f"Fire panel condition: {point.value}", priority=1, now=now)
        else:
            self._clear(key, now)

    def _evaluate_doors(self, points: PointStore, now: datetime) -> None:
        # Scans whatever doors access_control.py actually published, rather than a fixed
        # count — access_control.py's own poller already iterates the sim's real door
        # list with no limit, so a 4th door added there is covered here too, instead of
        # silently going unalarmed.
        for key, point in points.items():
            if not key.startswith("access-control.door"):
                continue
            if point.value is None:
                continue
            if point.value in ("FORCED", "HELD_OPEN"):
                self._raise(key, f"{point.name} is {point.value}", priority=2, now=now)
            else:
                self._clear(key, now)

    def _evaluate_fan_mismatch(self, points: PointStore, now: datetime) -> None:
        # sims/bacnet_devices/main.py mirrors fan_status from fan_command unconditionally
        # (no fault-injection path exists for a genuinely stuck/failed fan), so there's no
        # way to demo a *sustained* mismatch today. It does fire briefly and correctly in
        # practice, though: confirmed live by triggering the fire interlock and releasing
        # it — fan_command resolves back to the schedule's value over BACnet immediately
        # on relinquish, while the sim's own mirror line only catches up on its next poll
        # tick, producing a real (if momentary) disagreement the gateway alarms on and
        # then clears a few seconds later. Demoing a *sustained* mismatch (a genuinely
        # stuck fan) would need a fault-injection surface on the AHU sim, matching the
        # demo-trigger pattern the other three sims already have. Deliberately not built
        # here; see docs/alarm-engine-notes.md.
        key = "ahu-1.fan_mismatch"
        command = points.get("ahu-1.fan_command")
        status = points.get("ahu-1.fan_status")
        if command is None or status is None or command.value is None or status.value is None:
            return
        if command.value != status.value:
            self._raise(
                key,
                f"AHU-1 fan commanded {command.value} but status reads {status.value}",
                priority=2,
                now=now,
            )
        else:
            self._clear(key, now)

    def _evaluate_sat_deviation(self, points: PointStore, now: datetime) -> None:
        key = "ahu-1.sat_deviation"
        sat = points.get("ahu-1.sat")
        setpoint = points.get("ahu-1.sat_setpoint")
        if sat is None or setpoint is None or sat.value is None or setpoint.value is None:
            return
        deviation = abs(sat.value - setpoint.value)

        if deviation <= SAT_DEADBAND_C:
            self._deviation_since.pop(key, None)
            self._clear(key, now)
            return

        since = self._deviation_since.setdefault(key, now)
        if (now - since).total_seconds() >= SAT_DELAY_S:
            self._raise(
                key,
                f"AHU-1 SAT {sat.value:.1f}°C is {deviation:.1f}°C off setpoint "
                f"{setpoint.value:.1f}°C for {SAT_DELAY_S:.0f}s+",
                priority=3,
                now=now,
            )
