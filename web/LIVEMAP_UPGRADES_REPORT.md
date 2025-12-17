# SAHTD Live Map Upgrades Report

**Date:** 2025-12-17  
**Status:** ✅ Complete

---

## Summary

Upgraded the Live Map page with enhanced drone visualization features.

---

## Features Implemented

| Feature | Description |
|---------|-------------|
| **Trajectory Trail** | Last 30s of drone positions, fading with age (max 300 points) |
| **Reload Fence Button** | Re-fetch fence data on demand, shows ✓ on success |
| **Margin Band** | Semi-transparent stroke around fence showing soft margin |
| **Enhanced Legend** | Shows all visual elements |

---

## Files Modified

| File | Change |
|------|--------|
| `frontend/src/pages/MapPage.jsx` | Added trail buffer, reload fence, margin drawing |
| `frontend/src/index.css` | Added 56 lines for new controls |
| `ros2/.../telemetry_bridge_node.py` | Added Gazebo human pose polling (optional) |

---

## Map Visual Elements

```
┌─────────────────────────────────────────────┐
│                 Live Map                     │
├─────────────────────────────────────────────┤
│  ▪ Fence polygon (cyan line)                │
│  ▪ Margin band (semi-transparent outer)     │
│  ▪ Grid + axis labels (X=East, Y=North)     │
│  ▪ Origin marker (0,0)                      │
│  ▪ Drone dot (color-coded by status)        │
│  ▪ Heading arrow (yaw direction)            │
│  ▪ Trajectory trail (green, fading)         │
│  ▪ Position label with altitude             │
└─────────────────────────────────────────────┘
```

---

## Color Coding

| Color | Meaning |
|-------|---------|
| Green | Normal operation |
| Yellow | HOLD status or stale (>0.5s) |
| Red | VIOLATION or very stale (>2s) |

---

## Data Cards (8 total)

- Guard Status (color-coded)
- Follow State
- Inside Fence (YES/NO)
- Distance to Fence
- Position (x, y, z)
- Heading (yaw°)
- Target ID
- Update Age

---

## Run Commands

```bash
# Backend/Frontend unchanged
cd ~/sahtd/web/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd ~/sahtd/web/frontend && npm run dev -- --host 0.0.0.0 --port 5173

# Optional: ROS telemetry node (if collecting human poses)
cd ~/sahtd/ros2/src && colcon build --packages-select sahtd_web_bridge
ros2 run sahtd_web_bridge telemetry_bridge_node
```

---

## Access

- **URL:** `http://localhost:5173/app/map`
- **From Control Panel:** Click **Map** button
