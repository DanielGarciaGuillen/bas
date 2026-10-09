from app import state
from app.points import Point


def setup_function():
    state.points.clear()


def test_set_point_writes_the_full_shape():
    state.set_point("meter-1.kw", "meter-1", "kW Total", 18.0, "kW")
    assert state.points["meter-1.kw"] == Point(
        id="meter-1.kw", device="meter-1", name="kW Total", value=18.0, units="kW", status="ok"
    )


def test_fault_point_nulls_the_value_even_if_never_seen_before():
    state.fault_point("meter-1.kw", "meter-1", "kW Total", "kW")
    assert state.points["meter-1.kw"].value is None
    assert state.points["meter-1.kw"].status == "fault"


def test_fault_device_faults_every_known_point_for_that_device_only():
    state.set_point("access-control.door1", "access-control", "Main Entrance", "NORMAL")
    state.set_point("access-control.door2", "access-control", "Server Room", "NORMAL")
    state.set_point("fire-panel.condition", "fire-panel", "Panel Condition", "NORMAL")

    state.fault_device("access-control")

    assert state.points["access-control.door1"].status == "fault"
    assert state.points["access-control.door1"].value is None
    assert state.points["access-control.door2"].status == "fault"
    # A different device's point is untouched.
    assert state.points["fire-panel.condition"].status == "ok"


def test_fault_device_is_a_no_op_when_nothing_is_known_yet():
    state.fault_device("access-control")
    assert state.points == {}
