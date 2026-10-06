"""Fire alarm panel simulator — REST, not a field protocol.

A real fire alarm panel doesn't speak BACnet or Modbus to the BAS; monitoring/
annunciation is its own system, kept deliberately separate (see docs/fire-alarm-notes.md).
This simulates that boundary: a plain REST API the gateway polls, same shape as polling a
field protocol, but over HTTP.

Panel logic is in panel.py (pure, unit-tested); this file just wires it to FastAPI.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
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
from pydantic import BaseModel

app = FastAPI(title="Fire Alarm Panel Simulator")
panel = Panel()


class ZoneOut(BaseModel):
    id: int
    name: str
    condition: Literal["normal", "alarm", "trouble", "supervisory"]
    field_cleared: bool


class PanelOut(BaseModel):
    condition: Literal["normal", "alarm", "trouble", "supervisory"]
    any_alarm: bool
    acknowledged: bool
    silenced: bool
    zones: list[ZoneOut]


def _panel_out() -> PanelOut:
    return PanelOut(
        condition=overall_condition(panel),
        any_alarm=any_alarm(panel),
        acknowledged=panel.acknowledged,
        silenced=panel.silenced,
        zones=[ZoneOut(**vars(z)) for z in panel.zones.values()],
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/panel", response_model=PanelOut)
async def get_panel() -> PanelOut:
    return _panel_out()


class TriggerBody(BaseModel):
    condition: Literal["alarm", "trouble", "supervisory"]


@app.post("/zones/{zone_id}/trigger", response_model=PanelOut)
async def trigger_zone(zone_id: int, body: TriggerBody) -> PanelOut:
    if zone_id not in panel.zones:
        raise HTTPException(status_code=404, detail=f"no such zone: {zone_id}")
    trigger(panel, zone_id, body.condition)
    return _panel_out()


@app.post("/zones/{zone_id}/clear", response_model=PanelOut)
async def clear_zone(zone_id: int) -> PanelOut:
    if zone_id not in panel.zones:
        raise HTTPException(status_code=404, detail=f"no such zone: {zone_id}")
    clear_field(panel, zone_id)
    return _panel_out()


@app.post("/panel/acknowledge", response_model=PanelOut)
async def acknowledge_panel() -> PanelOut:
    acknowledge(panel)
    return _panel_out()


@app.post("/panel/silence", response_model=PanelOut)
async def silence_panel() -> PanelOut:
    silence(panel)
    return _panel_out()


@app.post("/panel/reset", response_model=PanelOut)
async def reset_panel() -> PanelOut:
    try:
        reset(panel)
    except ResetBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _panel_out()
