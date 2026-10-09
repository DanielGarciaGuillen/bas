from app.points import Point, fault, fault_device, numeric_points, publish


def test_publish_stores_by_point_id():
    store: dict = {}
    publish(
        store, Point(id="meter-1.kw", device="meter-1", name="kW Total", value=18.0, units="kW")
    )
    assert store["meter-1.kw"].value == 18.0
    assert store["meter-1.kw"].status == "ok"


def test_publish_overwrites_the_same_id():
    store: dict = {}
    publish(store, Point(id="x", device="d", name="n", value=1.0))
    publish(store, Point(id="x", device="d", name="n", value=2.0))
    assert store["x"].value == 2.0


def test_fault_nulls_the_value_even_if_never_published_before():
    store: dict = {}
    fault(store, "meter-1.kw", "meter-1", "kW Total", "kW")
    assert store["meter-1.kw"].value is None
    assert store["meter-1.kw"].status == "fault"
    assert store["meter-1.kw"].units == "kW"


def test_fault_device_faults_every_point_for_that_device_and_preserves_name_units():
    store: dict = {}
    publish(store, Point(id="d1", device="access-control", name="Main Entrance", value="NORMAL"))
    publish(store, Point(id="d2", device="access-control", name="Server Room", value="NORMAL"))
    publish(store, Point(id="fp", device="fire-panel", name="Panel Condition", value="NORMAL"))

    fault_device(store, "access-control")

    assert store["d1"].value is None
    assert store["d1"].status == "fault"
    assert store["d1"].name == "Main Entrance"  # name/units preserved, not blanked
    assert store["d2"].status == "fault"
    assert store["fp"].status == "ok"  # a different device is untouched


def test_numeric_points_filters_out_strings_and_none():
    store = {
        "a": Point(id="a", device="d", name="n", value=18.4),
        "b": Point(id="b", device="d", name="n", value="NORMAL"),
        "c": Point(id="c", device="d", name="n", value=None),
        "d": Point(id="d", device="d", name="n", value=0),  # 0 is numeric, not falsy-excluded
    }
    result = {p.id for p in numeric_points(store)}
    assert result == {"a", "d"}
