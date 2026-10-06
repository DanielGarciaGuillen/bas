"""BuildingOps Lab gateway.

Polls field devices (Modbus meter, BACnet AHU-1, the fire panel sim), normalizes them
into one point shape, and exposes them over REST. Access control lands in M5.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import bacnet_ahu, fire_panel, modbus_meter
from .state import points

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(modbus_meter.poll_meter_forever()),
        asyncio.create_task(bacnet_ahu.poll_ahu_forever()),
        asyncio.create_task(fire_panel.poll_fire_panel_forever()),
    ]
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
async def list_points() -> list[dict]:
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


# --- Fire panel: the console only ever talks to the gateway, never to the panel sim
# directly (same rule as everything else) — these just proxy through. ------------------


async def _proxy_to_fire_panel(method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(base_url=fire_panel.FIRE_PANEL_URL, timeout=5.0) as client:
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Fire panel unreachable: {exc}") from exc
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    return resp.json()


class TriggerZoneBody(BaseModel):
    condition: Literal["alarm", "trouble", "supervisory"]


@app.post("/fire-panel/zones/{zone_id}/trigger")
async def trigger_fire_zone(zone_id: int, body: TriggerZoneBody) -> dict:
    return await _proxy_to_fire_panel(
        "POST", f"/zones/{zone_id}/trigger", json={"condition": body.condition}
    )


@app.post("/fire-panel/zones/{zone_id}/clear")
async def clear_fire_zone(zone_id: int) -> dict:
    return await _proxy_to_fire_panel("POST", f"/zones/{zone_id}/clear")


@app.post("/fire-panel/acknowledge")
async def acknowledge_fire_panel() -> dict:
    return await _proxy_to_fire_panel("POST", "/panel/acknowledge")


@app.post("/fire-panel/silence")
async def silence_fire_panel() -> dict:
    return await _proxy_to_fire_panel("POST", "/panel/silence")


@app.post("/fire-panel/reset")
async def reset_fire_panel() -> dict:
    return await _proxy_to_fire_panel("POST", "/panel/reset")
