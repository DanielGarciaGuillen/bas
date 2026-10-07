"""Access control simulator — REST, same deliberate boundary as sims/fire_panel.

A real access control system doesn't speak BACnet or Modbus either; it's its own system
the gateway polls over REST, same shape as everything else.

Logic is in access.py (pure, unit-tested); this file just wires it to FastAPI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from access import (
    AccessControlSystem,
    any_alarm,
    badge,
    clear_door,
    force_open,
    hold_open,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Access Control Simulator")
system = AccessControlSystem()


class DoorOut(BaseModel):
    id: int
    name: str
    required_level: int
    state: Literal["normal", "forced", "held_open"]


class CardholderOut(BaseModel):
    id: int
    name: str
    access_level: int
    schedule: Literal["always", "business_hours"]


class EventOut(BaseModel):
    door_id: int
    cardholder_id: int | None
    result: Literal["granted", "denied_level", "denied_schedule", "forced", "held_open"]
    reason: str
    timestamp: datetime


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
async def get_state() -> dict:
    return {
        "any_alarm": any_alarm(system),
        "doors": [DoorOut(**vars(d)) for d in system.doors.values()],
        "cardholders": [CardholderOut(**vars(c)) for c in system.cardholders.values()],
    }


@app.get("/events", response_model=list[EventOut])
async def get_events(limit: int = 20) -> list[EventOut]:
    return [EventOut(**vars(e)) for e in system.events[-limit:][::-1]]


class BadgeBody(BaseModel):
    cardholder_id: int


@app.post("/doors/{door_id}/badge", response_model=EventOut)
async def badge_door(door_id: int, body: BadgeBody) -> EventOut:
    if door_id not in system.doors:
        raise HTTPException(status_code=404, detail=f"no such door: {door_id}")
    if body.cardholder_id not in system.cardholders:
        raise HTTPException(status_code=404, detail=f"no such cardholder: {body.cardholder_id}")
    event = badge(system, door_id, body.cardholder_id, datetime.now())
    return EventOut(**vars(event))


@app.post("/doors/{door_id}/force", response_model=EventOut)
async def force_door(door_id: int) -> EventOut:
    if door_id not in system.doors:
        raise HTTPException(status_code=404, detail=f"no such door: {door_id}")
    event = force_open(system, door_id, datetime.now())
    return EventOut(**vars(event))


@app.post("/doors/{door_id}/hold-open", response_model=EventOut)
async def hold_open_door(door_id: int) -> EventOut:
    if door_id not in system.doors:
        raise HTTPException(status_code=404, detail=f"no such door: {door_id}")
    event = hold_open(system, door_id, datetime.now())
    return EventOut(**vars(event))


@app.post("/doors/{door_id}/clear", response_model=DoorOut)
async def clear_door_endpoint(door_id: int) -> DoorOut:
    if door_id not in system.doors:
        raise HTTPException(status_code=404, detail=f"no such door: {door_id}")
    door = clear_door(system, door_id)
    return DoorOut(**vars(door))
