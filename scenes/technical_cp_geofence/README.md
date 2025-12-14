# Technical Checkpoint Scene 2: Geo-fence Demo

A deterministic Gazebo scene demonstrating human geo-fence violation detection with a playground area, multiple humans, and a "violator" who exits the fenced area.

> **Note:** The actors use `model://` URIs for mesh portability. `start_px4.sh` automatically sets `GZ_SIM_RESOURCE_PATH`.

## Quick Start

### 1. Start PX4 SITL with the scene world

```bash
cd ~/sahtd
PX4_GZ_WORLD=technical_cp_geofence ./scripts/core/start_px4.sh
```

Wait until you see the Gazebo window with:
- Grass-green ground plane
- Red rectangular playground border (~8m × 8m)
- 4 standing humans inside
- 2 walking actors (violator + inside walker)
- Drone spawned at (0, 0)

### 2. Start ROS perception + geofence nodes

In a **new terminal**:

```bash
cd ~/sahtd
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch sahtd_launch demo_follow.launch.py \
    world_name:=technical_cp_geofence \
    enable_geofence:=true \
    target_actor_name:=person_violator \
    geo_guard_params_file:=$(ros2 pkg prefix sahtd_launch)/share/sahtd_launch/config/geo_guard_geofence.yaml
```

**Key Args:**
- `enable_geofence:=true` - Enables geofence monitoring nodes
- `target_actor_name:=person_violator` - Actor to track for violations

## Verification Commands

### Check topics are publishing

```bash
ros2 topic list | egrep "guard|alerts|tracks"
```

Expected output includes:
- `/sahtd/guard/target_status`
- `/sahtd/guard/target_reason`
- `/sahtd/alerts`
- `/perception/tracks`

### Monitor violation status

```bash
ros2 topic echo /sahtd/guard/target_status
```

Expected sequence:
1. `TARGET_INSIDE_FENCE` - Violator starts inside
2. `TARGET_NEAR_EDGE` - Violator approaches edge
3. `TARGET_OUTSIDE_FENCE` - Violator exits (violation!)

### Watch for alerts

```bash
ros2 topic echo /sahtd/alerts
```

Expected: One-shot message when violation occurs:
```
data: 'HUMAN GEOFENCE VIOLATION: Target exited fence at (17.00, -2.00)'
```

### Check actor pose is being tracked

```bash
ros2 topic echo /gp2/target_pose_gt/info
```

## Record Evidence (Rosbag)

```bash
ros2 bag record -o ~/sahtd/bags/tc_scene2_geofence \
    /sahtd/guard/target_status \
    /sahtd/guard/target_reason \
    /sahtd/alerts \
    /perception/tracks \
    /gp2/target_pose_gt \
    -d 20
```

## Reset Scene

To restart the violation sequence (respawn violator at starting position):

```bash
~/sahtd/scenes/technical_cp_geofence/scripts/reset_scene.sh
```

## Scene Details

| Property | Value |
|----------|-------|
| World name | `technical_cp_geofence` |
| Fence boundary | x=8→16, y=-4→4 (8m × 8m) |
| Fence center | (12, 0) - 12m ahead of drone |
| Violator actor | `person_violator` |
| Violator exits at | ~12 seconds (x > 16) |
| Total actors | 6 (1 violator + 1 walker + 4 standing) |
| Drone spawn | (0, 0, 0) |

## Troubleshooting

### No violation detected

**Symptom:** `/sahtd/guard/target_status` remains `TARGET_INSIDE_FENCE`

**Possible causes:**
1. Actor pose not being tracked - check `/gp2/target_pose_gt/info`
2. Wrong target actor name - verify `target_actor_name:=person_violator`
3. Fence config wrong - check `geo_guard_params_file`

### Actor pose not publishing

**Symptom:** `/gp2/target_pose_gt` has no messages

**Fix:** Verify the actor exists in Gazebo:
```bash
gz model -m person_violator --world technical_cp_geofence
```

### Scene 1 behavior changed

If Scene 1 (tracking demo) now has geofence issues, ensure you're launching with:
```bash
ros2 launch sahtd_launch demo_follow.launch.py \
    world_name:=technical_cp_track \
    enable_geofence:=false
```
