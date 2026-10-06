"""BuildingOps Lab gateway.

Polls field devices (Modbus meter, BACnet AHU-1 so far), normalizes them into one point
shape, and exposes them over REST. Fire/access events land in later milestones.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import bacnet_ahu, modbus_meter
from .state import points

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(modbus_meter.poll_meter_forever()),
        asyncio.create_task(bacnet_ahu.poll_ahu_forever()),
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
