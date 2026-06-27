"""Ventilation dashboard backend.

Proxies Home Assistant (live states + limit helpers) and VictoriaMetrics
(history), and serves the static frontend. Holds the HA long-lived token so it
never reaches the browser.
"""
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN")
VM_URL = os.environ.get("VM_URL", "http://homeassistant.local:8428").rstrip("/")

if not HA_TOKEN:
    raise RuntimeError("HA_TOKEN is required — set it in dashboard/backend/.env")

HEADERS = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# Live entities shown as status cards.
STATUS_ENTITIES = {
    "bathroom_humidity": "sensor.t_h_inside_sonoff_bathroom_humidity",
    "bathroom_small_humidity": "sensor.t_h_inside_bathroom_small_humidity",
    "room_humidity": "sensor.t_h_inside_sonoff_bedroom_humidity",
    "fan_level": "pyscript.bathroom_fan_level",
    "dehumidifier": "switch.dehumidifier",
    "presence": "binary_sensor.presence_bathroom_occupancy",
}

# Editable limit helpers, ordered and grouped for the UI. Metadata
# (min/max/step/unit) is read live from HA, not duplicated here.
LIMITS = [
    {"group": "Dehumidifier", "name": "dehumidifier_off_humidity"},
    {"group": "Dehumidifier", "name": "presence_off_delay_sec"},
    {"group": "Fan thresholds", "name": "humidity_medium_fan"},
    {"group": "Fan thresholds", "name": "humidity_high_fan"},
    {"group": "Fan thresholds", "name": "humidity_max_fan"},
    {"group": "Fan thresholds", "name": "humidity_diff_ok"},
    {"group": "Fan timing", "name": "max_fan_run_time_min"},
    {"group": "Fan timing", "name": "fan_cooldown_min"},
    {"group": "Night window", "name": "night_start_hour"},
    {"group": "Night window", "name": "night_end_hour"},
]
ALLOWED_LIMITS = {item["name"] for item in LIMITS}

# History panels — PromQL against VictoriaMetrics (hass_ namespace).
PANELS = {
    "humidity": [
        {"label": "Bathroom", "query": 'hass_sensor_humidity_percent{entity="sensor.t_h_inside_sonoff_bathroom_humidity"}'},
        {"label": "Bathroom (small)", "query": 'hass_sensor_humidity_percent{entity="sensor.t_h_inside_bathroom_small_humidity"}'},
        {"label": "Bedroom", "query": 'hass_sensor_humidity_percent{entity="sensor.t_h_inside_sonoff_bedroom_humidity"}'},
    ],
    "dehumidifier": [
        {"label": "Dehumidifier", "query": 'hass_switch_state{entity="switch.dehumidifier"}'},
    ],
    "presence": [
        {"label": "Presence", "query": 'hass_binary_sensor_state{entity="binary_sensor.presence_bathroom_occupancy"}'},
    ],
}

app = FastAPI(title="Ventilation dashboard")


async def ha_get(client, path):
    r = await client.get(f"{HA_URL}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


@app.get("/api/status")
async def status():
    out = {}
    async with httpx.AsyncClient() as client:
        for key, entity in STATUS_ENTITIES.items():
            try:
                d = await ha_get(client, f"/api/states/{entity}")
                out[key] = {
                    "entity_id": entity,
                    "state": d.get("state"),
                    "attributes": d.get("attributes", {}),
                    "last_changed": d.get("last_changed"),
                }
            except Exception as e:  # surface per-entity, don't fail the whole call
                out[key] = {"entity_id": entity, "state": None, "error": str(e)}
    return out


@app.get("/api/limits")
async def get_limits():
    out = []
    async with httpx.AsyncClient() as client:
        for item in LIMITS:
            entity = f"input_number.{item['name']}"
            d = await ha_get(client, f"/api/states/{entity}")
            attrs = d.get("attributes", {})
            out.append({
                "name": item["name"],
                "group": item["group"],
                "value": float(d["state"]),
                "min": attrs.get("min"),
                "max": attrs.get("max"),
                "step": attrs.get("step"),
                "unit": attrs.get("unit_of_measurement", ""),
                "friendly_name": attrs.get("friendly_name", item["name"]),
            })
    return out


class LimitUpdate(BaseModel):
    name: str
    value: float


@app.post("/api/limits")
async def set_limit(upd: LimitUpdate):
    if upd.name not in ALLOWED_LIMITS:
        raise HTTPException(400, f"unknown limit: {upd.name}")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{HA_URL}/api/services/input_number/set_value",
            headers=HEADERS,
            json={"entity_id": f"input_number.{upd.name}", "value": upd.value},
            timeout=10,
        )
        r.raise_for_status()
    return {"ok": True, "name": upd.name, "value": upd.value}


@app.get("/api/history")
async def history(panel: str, minutes: int = 720):
    if panel not in PANELS:
        raise HTTPException(404, f"unknown panel: {panel}")
    end = int(time.time())
    start = end - minutes * 60
    step = max(15, (minutes * 60) // 800)  # cap at ~800 points
    series = []
    async with httpx.AsyncClient() as client:
        for s in PANELS[panel]:
            r = await client.get(
                f"{VM_URL}/api/v1/query_range",
                params={"query": s["query"], "start": start, "end": end, "step": step},
                timeout=20,
            )
            r.raise_for_status()
            result = r.json().get("data", {}).get("result", [])
            points = [[int(float(t)), float(v)] for t, v in result[0]["values"]] if result else []
            series.append({"label": s["label"], "points": points})
    return {"panel": panel, "start": start, "end": end, "step": step, "series": series}


# Static frontend (mounted last so /api/* routes win).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
