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


def test_starts_all_normal():
    panel = Panel()
    assert overall_condition(panel) == "normal"
    assert not any_alarm(panel)


def test_trigger_sets_condition_and_unclears_field():
    panel = Panel()
    trigger(panel, 4, "alarm")
    assert panel.zones[4].condition == "alarm"
    assert panel.zones[4].field_cleared is False
    assert overall_condition(panel) == "alarm"
    assert any_alarm(panel)


def test_overall_condition_priority_alarm_beats_trouble_beats_supervisory():
    panel = Panel()
    trigger(panel, 1, "trouble")
    trigger(panel, 2, "supervisory")
    assert overall_condition(panel) == "trouble"
    trigger(panel, 3, "alarm")
    assert overall_condition(panel) == "alarm"


def test_trigger_rejects_normal_as_a_condition():
    panel = Panel()
    with pytest.raises(ValueError):
        trigger(panel, 1, "normal")


def test_new_trigger_clears_acknowledge_and_silence():
    panel = Panel()
    trigger(panel, 1, "alarm")
    acknowledge(panel)
    silence(panel)
    assert panel.acknowledged and panel.silenced

    trigger(panel, 2, "alarm")
    assert panel.acknowledged is False
    assert panel.silenced is False


def test_reset_blocked_while_a_zone_is_still_active_and_not_field_cleared():
    panel = Panel()
    trigger(panel, 4, "alarm")
    with pytest.raises(ResetBlocked) as exc_info:
        reset(panel)
    assert panel.zones[4].condition == "alarm"  # unchanged
    assert exc_info.value.blocking_zones == [panel.zones[4]]


def test_reset_succeeds_once_field_is_cleared():
    panel = Panel()
    trigger(panel, 4, "alarm")
    clear_field(panel, 4)
    reset(panel)
    assert overall_condition(panel) == "normal"
    assert panel.zones[4].condition == "normal"
    assert panel.acknowledged is False
    assert panel.silenced is False


def test_reset_with_multiple_active_zones_needs_all_cleared():
    panel = Panel()
    trigger(panel, 1, "alarm")
    trigger(panel, 2, "trouble")
    clear_field(panel, 1)
    with pytest.raises(ResetBlocked) as exc_info:
        reset(panel)
    assert [z.id for z in exc_info.value.blocking_zones] == [2]

    clear_field(panel, 2)
    reset(panel)
    assert overall_condition(panel) == "normal"
