# SAHTD Telemetry Streaming Implementation Report

**Date:** 2025-12-17  
**Status:** ✅ Complete and Working

---

## Summary

Implemented real-time telemetry streaming from ROS2 to the web dashboard via a JSONL log file bridge pattern.

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  ROS2 Topics        │     │  telemetry.jsonl     │     │  Web Dashboard  │
│  (pose, guard,      │────▶│  (JSONL log file)    │────▶│  (React UI)     │
│   follow, etc.)     │     │                      │     │                 │
└─────────────────────┘     └──────────────────────┘     └─────────────────┘
         │                           │                           │
    telemetry_bridge_node      FastAPI /ws/state          AppShell.jsx
    (ROS2 Python node)         (tail -f style)           (WebSocket client)
```

---

## Components Created/Modified

### A) New ROS2 Package: `sahtd_web_bridge`

**Location:** `~/sahtd/ros2/src/sahtd_web_bridge/`

**Node:** `telemetry_bridge_node`

**Subscriptions:**
| Topic | Type | Status |
|-------|------|--------|
| `/gp2/vehicle/pose_local` | `PoseStamped` | Required |
| `/gp2/guard/status` | `String` | Optional |
| `/gp2/guard/inside` | `Bool` | Optional |
| `/gp2/guard/distance_to_fence` | `Float32` | Optional |
| `/sahtd/follow/state` | `String` | Optional |
| `/perception/target_select` | `Int32` | Optional |
| `/perception/seen_ids` | `String` | Optional |

**Parameters:**
- `write_hz` (default: 2.0) - Write rate to JSONL
- `telemetry_log_path` (default: `~/sahtd/data/logs/telemetry.jsonl`)

**Output JSONL format:**
```json
{
  "ts": "2025-12-17T16:50:00+00:00",
  "seq": 42,
  "follow_state": "FOLLOWING",
  "guard_status": "NORMAL",
  "inside": true,
  "distance_to_fence_m": 5.2,
  "pose": {"x": 1.5, "y": 2.3, "z": 10.0, "yaw_deg": 45.0},
  "selected_id": 3,
  "seen_ids": "1,3,5",
  "stale": {"pose_age_s": 0.1, "guard_age_s": 1.2, "follow_age_s": 0.5}
}
```

---

### B) Backend Changes

**File:** `~/sahtd/web/backend/app/main.py`

**Changes:**
- Added `TELEMETRY_LOG_PATH` environment variable
- Replaced mock `/ws/state` with real telemetry.jsonl tailing
- Version bumped to 0.4.0

**New behavior:**
- If `telemetry.jsonl` doesn't exist: sends "Waiting for telemetry log..." every 2s
- If file exists: tails it and streams each new line as JSON
- Handles file rotation gracefully

---

### C) Frontend Changes

**File:** `~/sahtd/web/frontend/src/pages/AppShell.jsx`

**New UI elements:**
- "Last telemetry: X ms ago" - computed from incoming `ts` field
- "Position: x=, y=, z=" - from `pose` object
- "Target ID:" - from `selected_id` field

---

## Run Commands

```bash
# 1. Build ROS2 package
cd ~/sahtd/ros2/src
source /opt/ros/humble/setup.bash
colcon build --packages-select sahtd_web_bridge
source install/setup.bash

# 2. Run telemetry bridge (needs ROS topics publishing)
ros2 run sahtd_web_bridge telemetry_bridge_node

# 3. Run backend
cd ~/sahtd/web/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Run frontend
cd ~/sahtd/web/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Dependencies Updated

**Backend (`requirements.txt`):**
- `uvicorn==0.38.0` (upgraded for Python 3.10 compatibility)
- `websockets==15.0.1` (upgraded - fixes asyncio.Lock() deprecation)

---

## Files Changed

| File | Action |
|------|--------|
| `ros2/src/sahtd_web_bridge/` | NEW - Entire package |
| `ros2/src/sahtd_web_bridge/package.xml` | NEW |
| `ros2/src/sahtd_web_bridge/setup.py` | NEW |
| `ros2/src/sahtd_web_bridge/sahtd_web_bridge/telemetry_bridge_node.py` | NEW |
| `web/backend/app/main.py` | MODIFIED - /ws/state streams telemetry.jsonl |
| `web/backend/requirements.txt` | MODIFIED - upgraded websockets, uvicorn |
| `web/frontend/src/pages/AppShell.jsx` | MODIFIED - added telemetry age, position, target ID |

---

## Next Steps (Suggested)

1. **Video streaming** - Add camera feed to dashboard (MJPEG or WebRTC)
2. **Mini-map** - Visualize drone position and fence on a 2D map
3. **ROS bridge for commands** - Connect /cmd/* endpoints to ROS topics
4. **Geofence visualization** - Show fence polygon on map
5. **Alert integration** - Publish geo-guard events to events.jsonl
