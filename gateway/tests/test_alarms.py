from datetime import datetime, timedelta

import pytest
from app.alarms import SAT_DEADBAND_C, SAT_DELAY_S, AlarmEngine, AlarmUnackable
from app.points import Point

T0 = datetime(2026, 10, 7, 12, 0, 0)


def point(point_id, device, name, value, units=None, status="ok"):
    return Point(id=point_id, device=device, name=name, value=value, units=units, status=status)


def base_points(**overrides):
    points = {
        "fire-panel.condition": point(
            "fire-panel.condition", "fire-panel", "Panel Condition", "NORMAL"
        ),
        "access-control.door1": point(
            "access-control.door1", "access-control", "Main Entrance", "NORMAL"
        ),
        "access-control.door2": point(
            "access-control.door2", "access-control", "Server Room", "NORMAL"
        ),
        "access-control.door3": point(
            "access-control.door3", "access-control", "Mechanical Room", "NORMAL"
        ),
        "ahu-1.fan_command": point("ahu-1.fan_command", "ahu-1", "Supply Fan Command", "active"),
        "ahu-1.fan_status": point("ahu-1.fan_status", "ahu-1", "Supply Fan Status", "active"),
        "ahu-1.sat": point("ahu-1.sat", "ahu-1", "Supply Air Temp", 13.0),
        "ahu-1.sat_setpoint": point("ahu-1.sat_setpoint", "ahu-1", "SAT Setpoint", 13.0),
    }
    points.update(overrides)
    return points


def test_no_alarms_on_a_fully_normal_system():
    engine = AlarmEngine()
    engine.evaluate(base_points(), T0)
    assert engine.active_alarms() == []


def test_fire_alarm_raised_and_cleared():
    engine = AlarmEngine()
    alarmed = base_points(
        **{
            "fire-panel.condition": point(
                "fire-panel.condition", "fire-panel", "Panel Condition", "ALARM"
            )
        }
    )
    engine.evaluate(alarmed, T0)
    [alarm] = engine.active_alarms()
    assert alarm.priority == 1
    assert alarm.state == "active_unacked"

    engine.evaluate(base_points(), T0 + timedelta(seconds=5))
    assert engine.active_alarms() == []
    assert engine.get(alarm.id).state == "cleared"


def test_fire_alarm_does_not_duplicate_while_still_active():
    engine = AlarmEngine()
    alarmed = base_points(
        **{
            "fire-panel.condition": point(
                "fire-panel.condition", "fire-panel", "Panel Condition", "ALARM"
            )
        }
    )
    engine.evaluate(alarmed, T0)
    engine.evaluate(alarmed, T0 + timedelta(seconds=5))
    engine.evaluate(alarmed, T0 + timedelta(seconds=10))
    assert len(engine.active_alarms()) == 1


def test_forced_door_raises_priority_2_alarm():
    engine = AlarmEngine()
    forced = base_points(
        **{
            "access-control.door2": point(
                "access-control.door2", "access-control", "Server Room", "FORCED"
            )
        }
    )
    engine.evaluate(forced, T0)
    [alarm] = engine.active_alarms()
    assert alarm.priority == 2
    assert "Server Room" in alarm.message


def test_forced_door_beyond_the_default_three_still_raises_an_alarm():
    # Regression for a hardcoded `(1, 2, 3)` door range that silently skipped any door
    # past the third — the rule now scans points by key prefix instead of a fixed count.
    engine = AlarmEngine()
    forced = base_points(
        **{
            "access-control.door4": point(
                "access-control.door4", "access-control", "Loading Dock", "FORCED"
            )
        }
    )
    engine.evaluate(forced, T0)
    [alarm] = engine.active_alarms()
    assert alarm.priority == 2
    assert "Loading Dock" in alarm.message


def test_fan_command_status_mismatch_raises_alarm():
    engine = AlarmEngine()
    mismatched = base_points(
        **{"ahu-1.fan_status": point("ahu-1.fan_status", "ahu-1", "Supply Fan Status", "inactive")}
    )
    engine.evaluate(mismatched, T0)
    [alarm] = engine.active_alarms()
    assert "mismatch" not in alarm.message  # message should be descriptive, not the word itself
    assert "commanded active" in alarm.message


def test_sat_deviation_needs_both_deadband_and_delay():
    engine = AlarmEngine()
    deviated = base_points(
        **{"ahu-1.sat": point("ahu-1.sat", "ahu-1", "Supply Air Temp", 13.0 + SAT_DEADBAND_C + 0.1)}
    )

    engine.evaluate(deviated, T0)
    assert engine.active_alarms() == []  # deadband exceeded, but not long enough yet

    engine.evaluate(deviated, T0 + timedelta(seconds=SAT_DELAY_S - 1))
    assert engine.active_alarms() == []

    engine.evaluate(deviated, T0 + timedelta(seconds=SAT_DELAY_S + 1))
    [alarm] = engine.active_alarms()
    assert alarm.priority == 3


def test_sat_deviation_within_deadband_never_alarms():
    engine = AlarmEngine()
    close_enough = base_points(
        **{"ahu-1.sat": point("ahu-1.sat", "ahu-1", "Supply Air Temp", 13.0 + SAT_DEADBAND_C - 0.1)}
    )
    for i in range(5):
        engine.evaluate(close_enough, T0 + timedelta(seconds=SAT_DELAY_S * i))
    assert engine.active_alarms() == []


def test_sat_deviation_timer_resets_if_it_recovers_before_the_delay():
    engine = AlarmEngine()
    deviated = base_points(**{"ahu-1.sat": point("ahu-1.sat", "ahu-1", "Supply Air Temp", 20.0)})
    engine.evaluate(deviated, T0)
    engine.evaluate(base_points(), T0 + timedelta(seconds=10))  # recovers
    engine.evaluate(deviated, T0 + timedelta(seconds=15))  # deviates again
    engine.evaluate(deviated, T0 + timedelta(seconds=15 + SAT_DELAY_S - 1))
    assert engine.active_alarms() == []  # the clock should have restarted at t=15


def test_ack_transitions_active_unacked_to_active_acked():
    engine = AlarmEngine()
    alarmed = base_points(
        **{
            "fire-panel.condition": point(
                "fire-panel.condition", "fire-panel", "Panel Condition", "ALARM"
            )
        }
    )
    engine.evaluate(alarmed, T0)
    [alarm] = engine.active_alarms()

    acked = engine.ack(alarm.id, T0 + timedelta(seconds=2))
    assert acked.state == "active_acked"
    assert acked.acked_at == T0 + timedelta(seconds=2)


def test_ack_rejects_an_already_acked_alarm():
    engine = AlarmEngine()
    alarmed = base_points(
        **{
            "fire-panel.condition": point(
                "fire-panel.condition", "fire-panel", "Panel Condition", "ALARM"
            )
        }
    )
    engine.evaluate(alarmed, T0)
    [alarm] = engine.active_alarms()
    engine.ack(alarm.id, T0)
    with pytest.raises(AlarmUnackable):
        engine.ack(alarm.id, T0)


def test_ack_rejects_unknown_alarm_id():
    engine = AlarmEngine()
    with pytest.raises(KeyError):
        engine.ack(999, T0)


def test_cleared_alarm_can_reopen_as_a_new_instance():
    engine = AlarmEngine()
    forced = base_points(
        **{
            "access-control.door1": point(
                "access-control.door1", "access-control", "Main Entrance", "FORCED"
            )
        }
    )
    engine.evaluate(forced, T0)
    [first] = engine.active_alarms()
    engine.evaluate(base_points(), T0 + timedelta(seconds=5))
    engine.evaluate(forced, T0 + timedelta(seconds=10))
    [second] = engine.active_alarms()
    assert second.id != first.id
    assert len(engine.all_alarms()) == 2
