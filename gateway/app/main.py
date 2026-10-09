"""BuildingOps Lab gateway.

Polls field devices (Modbus meter, BACnet AHU-1, the fire panel sim, access control),
normalizes them into one point shape, and exposes them over REST — plus, as of M6, an
alarm engine, trend history, and work orders (supervisor.py, alarms.py, db.py,
work_orders.py) that make it more than a polling pipe.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import partial
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import access_control, bacnet_ahu, db, fire_panel, modbus_meter, supervisor
from .alarms import AlarmUnackable
from .points import Point
from .poller import run_poller
from .state import alarm_engine, points, work_order_store
from .work_orders import WorkOrderNotFound, seed_preventive_maintenance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# (display name, poll interval, read(), logger) — one row per device module. Adding a
# 5th sim is a row here, not a new copy of the poll-loop shape; see poller.py.
POLLERS = [
    ("Modbus meter", modbus_meter.POLL_INTERVAL_S, modbus_meter.read, modbus_meter.log),
    ("AHU-1", bacnet_ahu.POLL_INTERVAL_S, bacnet_ahu.read, bacnet_ahu.log),
    ("Fire panel", fire_panel.POLL_INTERVAL_S, fire_panel.read, fire_panel.log),
    ("Access control", access_control.POLL_INTERVAL_S, access_control.read, access_control.log),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_preventive_maintenance(work_order_store, datetime.now())
    tasks = [
        asyncio.create_task(run_poller(name, interval_s, read_fn, points, log))
        for name, interval_s, read_fn, log in POLLERS
    ]
    tasks.append(asyncio.create_task(supervisor.run_supervisor_forever()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()


app = FastAPI(title="BuildingOps Lab Gateway", lifespan=lifespan)

# Lab-only: the console (localhost:5173) is a different origin from the gateway
# (localhost:8000), and there's no auth here to protect — wide open is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/points")
async def list_points() -> list[Point]:
    return list(points.values())


class SetpointWrite(BaseModel):
    value: float


@app.post("/ahu-1/setpoint")
async def write_ahu1_setpoint(body: SetpointWrite) -> dict:
    try:
        await bacnet_ahu.write_sat_setpoint(body.value)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"BACnet write failed: {exc}") from exc
    return {"id": "ahu-1.sat_setpoint", "value": body.value}


@app.post("/ahu-1/static-pressure-setpoint")
async def write_ahu1_static_pressure_setpoint(body: SetpointWrite) -> dict:
    try:
        await bacnet_ahu.write_static_pressure_setpoint(body.value)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"BACnet write failed: {exc}") from exc
    return {"id": "ahu-1.static_pressure_setpoint", "value": body.value}


# --- Simulators with a demo-control REST API: the console only ever talks to the
# gateway, never to a sim directly (same rule as everything else) — these just proxy
# through, so there's one generic proxy helper rather than one per sim.
#
# Each route below stays its own `@app.{method}` declaration — not a generic
# `{path:path}` catch-all — on purpose: the explicit list is functionally an allowlist
# (only these specific sim operations are reachable from the console), and keeping each
# route named gets FastAPI's per-route request validation and OpenAPI docs for free.
# What's declarative is the *binding*: `fire_panel_proxy`/`access_control_proxy` below
# are `_proxy` pre-bound to one service's name and base URL via `partial`, so neither
# gets retyped at each of this file's 13 call sites the way they used to (and a
# mismatched pair — right URL, wrong name, or vice versa — can no longer happen; there's
# only one of each left to get wrong). ------------------------------------------------


async def _proxy(service_name: str, base_url: str, method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail=f"{service_name} unreachable: {exc}"
            ) from exc
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    return resp.json()


fire_panel_proxy = partial(_proxy, "Fire panel", fire_panel.FIRE_PANEL_URL)
access_control_proxy = partial(_proxy, "Access control", access_control.ACCESS_CONTROL_URL)


class TriggerZoneBody(BaseModel):
    condition: Literal["alarm", "trouble", "supervisory"]


@app.post("/fire-panel/zones/{zone_id}/trigger")
async def trigger_fire_zone(zone_id: int, body: TriggerZoneBody) -> dict:
    return await fire_panel_proxy(
        "POST", f"/zones/{zone_id}/trigger", json={"condition": body.condition}
    )


@app.post("/fire-panel/zones/{zone_id}/clear")
async def clear_fire_zone(zone_id: int) -> dict:
    return await fire_panel_proxy("POST", f"/zones/{zone_id}/clear")


@app.post("/fire-panel/acknowledge")
async def acknowledge_fire_panel() -> dict:
    return await fire_panel_proxy("POST", "/panel/acknowledge")


@app.post("/fire-panel/silence")
async def silence_fire_panel() -> dict:
    return await fire_panel_proxy("POST", "/panel/silence")


@app.post("/fire-panel/reset")
async def reset_fire_panel() -> dict:
    return await fire_panel_proxy("POST", "/panel/reset")


@app.get("/fire-panel/panel")
async def get_fire_panel() -> dict:
    # Acknowledged/silenced are panel UI state, not a sensor reading — not worth
    # threading through the point model for two booleans the annunciator needs directly.
    return await fire_panel_proxy("GET", "/panel")


@app.get("/fire-panel/events")
async def list_fire_panel_events(limit: int = 20) -> list:
    return await fire_panel_proxy("GET", "/events", params={"limit": limit})


# --- Access control -------------------------------------------------------------------


class BadgeBody(BaseModel):
    cardholder_id: int


@app.post("/access-control/doors/{door_id}/badge")
async def badge_door(door_id: int, body: BadgeBody) -> dict:
    return await access_control_proxy(
        "POST", f"/doors/{door_id}/badge", json={"cardholder_id": body.cardholder_id}
    )


@app.post("/access-control/doors/{door_id}/force")
async def force_door(door_id: int) -> dict:
    return await access_control_proxy("POST", f"/doors/{door_id}/force")


@app.post("/access-control/doors/{door_id}/hold-open")
async def hold_open_door(door_id: int) -> dict:
    return await access_control_proxy("POST", f"/doors/{door_id}/hold-open")


@app.post("/access-control/doors/{door_id}/clear")
async def clear_door(door_id: int) -> dict:
    return await access_control_proxy("POST", f"/doors/{door_id}/clear")


@app.get("/access-control/cardholders")
async def list_cardholders() -> dict:
    return await access_control_proxy("GET", "/state")


@app.get("/access-control/events")
async def list_access_events(limit: int = 20) -> list:
    return await access_control_proxy("GET", "/events", params={"limit": limit})


# --- Alarms --------------------------------------------------------------------------


@app.get("/alarms")
async def list_alarms(active_only: bool = False) -> list:
    return alarm_engine.active_alarms() if active_only else alarm_engine.all_alarms()


@app.post("/alarms/{alarm_id}/ack")
async def ack_alarm(alarm_id: int):
    try:
        return alarm_engine.ack(alarm_id, datetime.now())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlarmUnackable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class WorkOrderFromAlarmBody(BaseModel):
    asset: str
    problem: str
    priority: int = 3
    notes: str = ""


@app.post("/alarms/{alarm_id}/work-order")
async def create_work_order_from_alarm(alarm_id: int, body: WorkOrderFromAlarmBody):
    if alarm_engine.get(alarm_id) is None:
        raise HTTPException(status_code=404, detail=f"no such alarm: {alarm_id}")
    return work_order_store.create(
        asset=body.asset,
        problem=body.problem,
        priority=body.priority,
        now=datetime.now(),
        notes=body.notes,
        source_alarm_id=alarm_id,
    )


# --- Work orders -----------------------------------------------------------------------


@app.get("/work-orders")
async def list_work_orders() -> list:
    return work_order_store.all()


class WorkOrderCreateBody(BaseModel):
    asset: str
    problem: str
    priority: int = 3
    notes: str = ""


@app.post("/work-orders")
async def create_work_order(body: WorkOrderCreateBody):
    return work_order_store.create(
        asset=body.asset,
        problem=body.problem,
        priority=body.priority,
        now=datetime.now(),
        notes=body.notes,
    )


class WorkOrderStatusBody(BaseModel):
    status: Literal["open", "in_progress", "done"]


@app.patch("/work-orders/{work_order_id}")
async def update_work_order(work_order_id: int, body: WorkOrderStatusBody):
    try:
        return work_order_store.set_status(work_order_id, body.status)
    except WorkOrderNotFound as exc:
        raise HTTPException(status_code=404, detail=f"no such work order: {exc}") from exc


# --- Trend history ---------------------------------------------------------------------


@app.get("/history/{point_id}")
async def get_history(point_id: str, minutes: int = 60, limit: int = 2000) -> list[dict]:
    end = datetime.now()
    start = end - timedelta(minutes=minutes)
    return await db.query_history(point_id, start, end, limit)
