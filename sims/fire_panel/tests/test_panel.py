from datetime import datetime

import pytest
from panel import (
    Panel,
    ResetBlocked,
    acknowledge,
    any_alarm,
    clear_field,
    overall_condition,
    reset,
    silence,
    trigger,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


def test_starts_all_normal():
    panel = Panel()
    assert overall_condition(panel) == "normal"
    assert not any_alarm(panel)


def test_trigger_sets_condition_and_unclears_field():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    assert panel.zones[4].condition == "alarm"
    assert panel.zones[4].field_cleared is False
    assert overall_condition(panel) == "alarm"
    assert any_alarm(panel)


def test_overall_condition_priority_alarm_beats_trouble_beats_supervisory():
    panel = Panel()
    trigger(panel, 1, "trouble", NOW)
    trigger(panel, 2, "supervisory", NOW)
    assert overall_condition(panel) == "trouble"
    trigger(panel, 3, "alarm", NOW)
    assert overall_condition(panel) == "alarm"


def test_trigger_rejects_normal_as_a_condition():
    panel = Panel()
    with pytest.raises(ValueError):
        trigger(panel, 1, "normal", NOW)


def test_new_trigger_clears_acknowledge_and_silence():
    panel = Panel()
    trigger(panel, 1, "alarm", NOW)
    acknowledge(panel, NOW)
    silence(panel, NOW)
    assert panel.acknowledged and panel.silenced

    trigger(panel, 2, "alarm", NOW)
    assert panel.acknowledged is False
    assert panel.silenced is False


def test_reset_blocked_while_a_zone_is_still_active_and_not_field_cleared():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    with pytest.raises(ResetBlocked) as exc_info:
        reset(panel, NOW)
    assert panel.zones[4].condition == "alarm"  # unchanged
    assert exc_info.value.blocking_zones == [panel.zones[4]]


def test_reset_succeeds_once_field_is_cleared():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    clear_field(panel, 4, NOW)
    reset(panel, NOW)
    assert overall_condition(panel) == "normal"
    assert panel.zones[4].condition == "normal"
    assert panel.acknowledged is False
    assert panel.silenced is False


def test_reset_with_multiple_active_zones_needs_all_cleared():
    panel = Panel()
    trigger(panel, 1, "alarm", NOW)
    trigger(panel, 2, "trouble", NOW)
    clear_field(panel, 1, NOW)
    with pytest.raises(ResetBlocked) as exc_info:
        reset(panel, NOW)
    assert [z.id for z in exc_info.value.blocking_zones] == [2]

    clear_field(panel, 2, NOW)
    reset(panel, NOW)
    assert overall_condition(panel) == "normal"


def test_trigger_appends_an_event():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    assert len(panel.events) == 1
    event = panel.events[0]
    assert event.kind == "trigger"
    assert event.zone_id == 4
    assert "alarm" in event.detail
    assert event.timestamp == NOW


def test_full_lifecycle_appends_one_event_per_action_in_order():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    acknowledge(panel, NOW)
    silence(panel, NOW)
    clear_field(panel, 4, NOW)
    reset(panel, NOW)
    assert [e.kind for e in panel.events] == [
        "trigger",
        "acknowledge",
        "silence",
        "clear",
        "reset",
    ]


def test_reset_blocked_does_not_append_a_reset_event():
    panel = Panel()
    trigger(panel, 4, "alarm", NOW)
    with pytest.raises(ResetBlocked):
        reset(panel, NOW)
    assert [e.kind for e in panel.events] == ["trigger"]
