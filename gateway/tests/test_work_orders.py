from datetime import datetime

import pytest
from app.work_orders import WorkOrderNotFound, WorkOrderStore, seed_preventive_maintenance

T0 = datetime(2026, 10, 7, 12, 0, 0)


def test_store_starts_empty():
    store = WorkOrderStore()
    assert store.all() == []


def test_create_assigns_increasing_ids_and_defaults_to_open():
    store = WorkOrderStore()
    first = store.create("ahu-1", "filter change", priority=4, now=T0)
    second = store.create("fire-panel", "inspection", priority=2, now=T0)
    assert first.id == 1
    assert second.id == 2
    assert first.status == "open"


def test_set_status_updates_in_place():
    store = WorkOrderStore()
    wo = store.create("ahu-1", "filter change", priority=4, now=T0)
    updated = store.set_status(wo.id, "in_progress")
    assert updated.status == "in_progress"
    assert store.get(wo.id).status == "in_progress"


def test_set_status_on_unknown_id_raises():
    store = WorkOrderStore()
    with pytest.raises(WorkOrderNotFound):
        store.set_status(999, "done")


def test_create_can_link_back_to_an_originating_alarm():
    store = WorkOrderStore()
    wo = store.create("ahu-1", "fan mismatch", priority=2, now=T0, source_alarm_id=7)
    assert wo.source_alarm_id == 7


def test_seed_preventive_maintenance_creates_two_open_work_orders():
    store = WorkOrderStore()
    seed_preventive_maintenance(store, T0)
    orders = store.all()
    assert len(orders) == 2
    assert all(o.status == "open" for o in orders)
    assert {o.asset for o in orders} == {"ahu-1", "fire-panel"}
