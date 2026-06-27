# Bathroom Ventilation Dashboard

Local web dashboard for the bathroom ventilation/dehumidifier pyscript automation:

- **Live status** — bathroom/room humidity, fan level, dehumidifier on/off, presence.
- **History graphs** — humidity, dehumidifier, presence (from VictoriaMetrics).
- **Editable limits** — the tunables that used to be hardcoded constants in
  `pyscript/bathroom.py`, backed by HA `input_number` helpers
  (`ha-config/ventilation_limits.yaml`). Edits save to HA instantly and take
  effect on the next pyscript run.

## Architecture

```
browser ──> FastAPI backend (holds HA token) ──> Home Assistant REST API (status + limits)
                                            └──> VictoriaMetrics  (history graphs)
```

The backend holds the HA token so it never reaches the browser, and serves the
static frontend (so no CORS).

## Setup

1. Create a **long-lived access token** in HA: your profile → Security →
   *Long-lived access tokens* → Create. Name it e.g. `ventilation-dashboard`.
2. Configure env:
   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env and paste the token into HA_TOKEN
   ```
   `.env` is gitignored — never commit it. Adjust `HA_URL` / `VM_URL` to the
   Tailscale hostname when running off-LAN (`homeassistant.local` is LAN-only).
3. Run:
   ```bash
   ./run.sh
   ```
   Open http://localhost:8099

## Notes

- History comes from VictoriaMetrics (`hass_` Prometheus namespace). It only has
  data for what HA's `prometheus:` integration exposes.
- Fan-level history isn't graphed (it's a string state); current level shows live.
- Limit values persist across HA restarts via `restore_state` (no `initial:` set
  on the helpers).
