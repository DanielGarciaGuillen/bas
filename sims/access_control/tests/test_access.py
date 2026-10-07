from datetime import datetime

from access import (
    AccessControlSystem,
    any_alarm,
    badge,
    clear_door,
    force_open,
    hold_open,
    within_schedule,
)

MAIN_ENTRANCE = 1
SERVER_ROOM = 2
MECHANICAL_ROOM = 3

ALICE_FACILITIES = 1  # level 3, always
BOB_STAFF = 2  # level 1, business_hours
CARLA_IT = 3  # level 2, business_hours
PRIYA_SECURITY = 5  # level 2, always
EVAN_CLEANER = 6  # level 1, always

A_WEEKDAY_NOON = datetime(2026, 10, 7, 12, 0)  # Wednesday
A_WEEKDAY_NIGHT = datetime(2026, 10, 7, 23, 0)
A_WEEKEND_NOON = datetime(2026, 10, 10, 12, 0)  # Saturday


def test_fresh_system_has_three_doors_and_six_cardholders():
    system = AccessControlSystem()
    assert len(system.doors) == 3
    assert len(system.cardholders) == 6
    assert system.events == []


def test_systems_do_not_share_mutable_state():
    """Regression guard for the exact bug class caught in sims/fire_panel/panel.py."""
    a = AccessControlSystem()
    b = AccessControlSystem()
    force_open(a, MAIN_ENTRANCE, A_WEEKDAY_NOON)
    assert a.doors[MAIN_ENTRANCE].state == "forced"
    assert b.doors[MAIN_ENTRANCE].state == "normal"


def test_badge_granted_for_sufficient_level_and_schedule():
    system = AccessControlSystem()
    event = badge(system, MAIN_ENTRANCE, BOB_STAFF, A_WEEKDAY_NOON)
    assert event.result == "granted"
    assert system.doors[MAIN_ENTRANCE].state == "normal"


def test_badge_denied_for_insufficient_level():
    system = AccessControlSystem()
    event = badge(system, SERVER_ROOM, EVAN_CLEANER, A_WEEKDAY_NOON)
    assert event.result == "denied_level"


def test_badge_denied_outside_schedule():
    system = AccessControlSystem()
    event = badge(system, MAIN_ENTRANCE, BOB_STAFF, A_WEEKDAY_NIGHT)
    assert event.result == "denied_schedule"


def test_badge_granted_for_always_schedule_at_night():
    system = AccessControlSystem()
    event = badge(system, SERVER_ROOM, PRIYA_SECURITY, A_WEEKDAY_NIGHT)
    assert event.result == "granted"


def test_facilities_manager_can_access_every_door_anytime():
    system = AccessControlSystem()
    for door_id in (MAIN_ENTRANCE, SERVER_ROOM, MECHANICAL_ROOM):
        assert badge(system, door_id, ALICE_FACILITIES, A_WEEKEND_NOON).result == "granted"


def test_it_staff_can_reach_server_room_but_not_mechanical_room():
    system = AccessControlSystem()
    assert badge(system, SERVER_ROOM, CARLA_IT, A_WEEKDAY_NOON).result == "granted"
    assert badge(system, MECHANICAL_ROOM, CARLA_IT, A_WEEKDAY_NOON).result == "denied_level"


def test_within_schedule_rejects_weekends_even_for_business_hours_cardholders():
    system = AccessControlSystem()
    bob = system.cardholders[BOB_STAFF]
    assert within_schedule(bob, A_WEEKDAY_NOON) is True
    assert within_schedule(bob, A_WEEKEND_NOON) is False


def test_force_open_sets_door_state_and_raises_alarm():
    system = AccessControlSystem()
    event = force_open(system, SERVER_ROOM, A_WEEKDAY_NOON)
    assert event.result == "forced"
    assert system.doors[SERVER_ROOM].state == "forced"
    assert any_alarm(system)


def test_hold_open_sets_door_state_and_raises_alarm():
    system = AccessControlSystem()
    hold_open(system, MECHANICAL_ROOM, A_WEEKDAY_NOON)
    assert system.doors[MECHANICAL_ROOM].state == "held_open"
    assert any_alarm(system)


def test_clear_door_resets_state_and_silences_alarm():
    system = AccessControlSystem()
    force_open(system, MAIN_ENTRANCE, A_WEEKDAY_NOON)
    assert any_alarm(system)
    clear_door(system, MAIN_ENTRANCE)
    assert system.doors[MAIN_ENTRANCE].state == "normal"
    assert not any_alarm(system)


def test_events_accumulate_in_order():
    system = AccessControlSystem()
    badge(system, MAIN_ENTRANCE, BOB_STAFF, A_WEEKDAY_NOON)
    force_open(system, SERVER_ROOM, A_WEEKDAY_NOON)
    assert [e.result for e in system.events] == ["granted", "forced"]
