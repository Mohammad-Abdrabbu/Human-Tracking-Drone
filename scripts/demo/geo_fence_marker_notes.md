# Geo-Fence Marker Analysis Notes

## Summary

This document describes the geo-fence polygon configuration used by `geo_guard_node` and confirms alignment with the drone pose coordinate system.

---

## A) GeoGuard Polygon Configuration

### YAML Paths

| Config File | Usage | Polygon Size |
|-------------|-------|--------------|
| `ros2/src/sahtd_launch/config/geo_guard.yaml` | Default (used by `demo_committee.sh`) | 14m × 14m |
| `scenes/technical_cp_geofence/config/geo_guard.yaml` | Scene-specific geofence demo | 24m × 24m |
| `ros2/src/sahtd_launch/config/geo_guard_geofence.yaml` | Alternative geofence config | 24m × 24m |

### Default Polygon (`geo_guard.yaml`)

```yaml
geo_guard_node:
  ros__parameters:
    vertices: [-7.0, -7.0,  7.0, -7.0,  7.0, 7.0,  -7.0, 7.0]
    soft_margin_m: 0.80
    hard_margin_m: 0.30
```

**Vertex list (order: CCW from bottom-left):**
- V0: (-7, -7)
- V1: (7, -7)
- V2: (7, 7)
- V3: (-7, 7)

**Notes:**
- Vertices stored as flat array: `[x0, y0, x1, y1, ...]`
- Parsed as pairs: `zip(arr[0::2], arr[1::2])`
- Total: 4 vertices (rectangular polygon)

### Frame Assumption

- **Frame:** ENU (East-North-Up)
- **Matches:** `/gp2/vehicle/pose_local` topic (drone's local position)
- **Origin:** (0, 0) is the world origin where drone spawns

---

## B) Runtime Alignment Verification

### Debug Topic

The `geo_guard_node` publishes detailed debug info to `/gp2/guard/debug`:

```
state=NORMAL enabled=true inside=true dist_m=5.42 soft_m=0.80 hard_m=0.30 pose=(x=0.15,y=-0.02) nearest_edge=0
```

### Key Fields

| Field | Description |
|-------|-------------|
| `state` | NORMAL / GEOGUARD_HOLD / GEOGUARD_VIOLATION |
| `inside` | true if drone is inside polygon |
| `dist_m` | Distance to nearest polygon edge (meters) |
| `pose` | Drone position (x, y) in ENU |
| `nearest_edge` | Index of nearest polygon edge (0-indexed) |

### Verification Command

```bash
ros2 topic echo /gp2/guard/debug --once
```

### Coordinate Space Confirmation

✅ The polygon vertices and pose coordinates are in the **same ENU map frame**:
- Polygon uses meters in ENU (x = East, y = North)
- `/gp2/vehicle/pose_local` uses the same ENU frame
- No rotation or offset needed for marker placement

---

## C) Marker Spawning Strategy

### Parameters for Markers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--z` | 0.05 | Height above ground (m) |
| `--radius` | 0.12 | Cylinder radius (m) |
| `--height` | 0.20 | Cylinder height (m) |
| `--prefix` | `fence_marker` | Model name prefix |

### Marker Positions

For 4-vertex default polygon:
- `fence_marker_v0` at (-7, -7, 0.05)
- `fence_marker_v1` at (7, -7, 0.05)
- `fence_marker_v2` at (7, 7, 0.05)
- `fence_marker_v3` at (-7, 7, 0.05)

---

## D) Related Files

| File | Purpose |
|------|---------|
| `ros2/src/sahtd_autonomy/sahtd_autonomy/control/geo_guard_node.py` | GeoGuard implementation |
| `ros2/src/sahtd_launch/launch/demo_follow.launch.py` | Default launch with geo_guard_params_file |
| `scripts/demo/demo_committee.sh` | Demo orchestrator |
| `scripts/sim/spawn_actor.sh` | Reference for gz service create API |
