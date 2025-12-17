# SAHTD Mini-Map Implementation Report

**Date:** 2025-12-17  
**Status:** ✅ Complete

---

## Summary

Added a dedicated **Live Map** page to the SAHTD web dashboard that displays the drone position and geo-fence boundary in real-time.

---

## New Files

| File | Description |
|------|-------------|
| `frontend/src/pages/MapPage.jsx` | Dedicated map page with large canvas and data cards |

## Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Added `GET /guard/fence` endpoint + `yaml` import |
| `backend/.env` | Added `FENCE_YAML_PATH` variable |
| `frontend/src/App.jsx` | Added `/app/map` route |
| `frontend/src/pages/AppShell.jsx` | Added Map nav button |
| `frontend/src/pages/TelemetryPage.jsx` | Added Map link, removed embedded mini-map |
| `frontend/src/index.css` | Added MapPage styles |

---

## Backend: `/guard/fence` Endpoint

**URL:** `GET /guard/fence`

**Source:** Reads from `geo_guard.yaml` (configurable via `FENCE_YAML_PATH`)

**Response:**
```json
{
  "frame": "ENU",
  "vertices": [{"x": -2.0, "y": -8.0}, {"x": 15.0, "y": -8.0}, ...],
  "closed": true,
  "margin_m": 0.8
}
```

---

## Frontend: Map Page Features

### Data Cards (2 rows x 4 columns)
- Guard Status (color-coded border)
- Follow State
- Inside Fence (YES/NO)
- Distance to Fence
- Position (x, y, z)
- Heading (yaw°)
- Target ID
- Update Age

### Canvas Visualization
- **Fence polygon** (cyan stroke + semi-transparent fill)
- **Fence vertices** (small dots)
- **Grid lines** with coordinate labels
- **Origin marker** (0,0) with dashed cross
- **Drone position** (large dot with glow effect)
- **Heading arrow** (points in yaw direction)
- **Axis labels** (X→East, Y→North)

### Color Coding
| Color | Meaning |
|-------|---------|
| Green | Normal operation |
| Yellow | HOLD status or stale data (>0.5s) |
| Red | VIOLATION status or very stale (>2s) |

### Legend
Shows color meanings at bottom of page.

---

## Navigation

```
┌─────────────────┐
│  Control Panel  │ ──→ [Map] [Telemetry] [Logout]
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌───────────┐
│  Map  │  │ Telemetry │
└───────┘  └───────────┘
```

---

## Run Commands

```bash
# Backend (set env var in .env, then restart)
cd ~/sahtd/web/backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (auto-reloads)
cd ~/sahtd/web/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Access

- **Direct URL:** `http://localhost:5173/app/map`
- **From Control Panel:** Click **Map** button
- **From Telemetry:** Click **Map** link
