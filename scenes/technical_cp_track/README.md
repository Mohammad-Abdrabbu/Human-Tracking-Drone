# Technical Checkpoint Scene 1: Tracking Demo

A deterministic Gazebo scene for tracking/following demonstration with a walking human actor on a zigzag path.

> **Note:** The actor uses `model://` URIs for mesh portability. `start_px4.sh` automatically sets `GZ_SIM_RESOURCE_PATH` to include `simulation/models`.

## Quick Start

### 1. Start PX4 SITL with the scene world

```bash
cd ~/sahtd
PX4_GZ_WORLD=technical_cp_track ./scripts/core/start_px4.sh
```

Wait until you see the Gazebo window with:
- Grass-green ground plane
- Gray sidewalk loop (rectangular, ~20m x 16m)
- Walking human actor circling the path
- Drone spawned at center (0, 0)

### 2. Start ROS perception + follow nodes

In a **new terminal**:

```bash
cd ~/sahtd
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch sahtd_launch demo_follow.launch.py \
    world_name:=technical_cp_track \
    enable_geofence:=false
```

**Important:** `enable_geofence:=false` disables the geo-guard node for this scene.

### 3. (Optional) Spawn actor if not visible

The actor is embedded in the world SDF and should appear automatically. If not:

```bash
~/sahtd/scenes/technical_cp_track/scripts/spawn_scene.sh
```

## Verification Commands

### Check topics are publishing

```bash
ros2 topic list | egrep "camera|tracks|target_select|hud|guard"
```

Expected output includes:
- `/camera/image_raw`
- `/perception/tracks`
- `/perception/debug_image_tracks`

### Check perception FPS

```bash
ros2 topic hz /perception/tracks
```

Expected: ~10-20 Hz

### Check follow node HUD

```bash
ros2 topic echo --once /sahtd/follow/hud
```

### Confirm geo-fence is OFF

```bash
ros2 node list | grep guard
```

Expected: **No output** (geo_guard_node should NOT be running)

## Record Evidence (Rosbag)

```bash
ros2 bag record -o ~/sahtd/bags/tc_scene1_demo \
    /camera/image_raw \
    /perception/tracks \
    /perception/target_select \
    /perception/debug_image_tracks \
    -d 20
```

## Troubleshooting

### Camera topic not receiving data

**Symptom:** `/camera/image_raw` has 0 Hz

**Cause:** World name mismatch between PX4 and ROS launch.

**Fix:** Ensure both use the same world name:
- PX4: `PX4_GZ_WORLD=technical_cp_track`
- ROS: `world_name:=technical_cp_track`

Check available Gazebo topics:
```bash
gz topic -l | grep image
```

### Actor didn't spawn

**Symptom:** No walking human visible in Gazebo.

**Cause:** Actor SDF failed to load or path incorrect.

**Fix:**
1. Check if actor is in world:
   ```bash
   gz model -m person_track --world technical_cp_track
   ```
2. Manually spawn:
   ```bash
   ~/sahtd/scenes/technical_cp_track/scripts/spawn_scene.sh
   ```
3. Check GZ_SIM_RESOURCE_PATH includes scene folder:
   ```bash
   export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:/home/ramadan/sahtd/scenes/technical_cp_track
   ```

### FPS drops below 5 Hz

**Symptom:** YOLO processing too slow, detections lagging.

**Cause:** CPU overloaded or Gazebo rendering too heavy.

**Fixes:**
1. Reduce Gazebo real-time factor:
   ```bash
   gz physics -w technical_cp_track --real-time-factor 0.5
   ```
2. Close unnecessary applications
3. Check YOLO model is using optimized weights

### Reset the scene

To reset the actor to starting position:

```bash
~/sahtd/scenes/technical_cp_track/scripts/reset_scene.sh
```

## Scene Details

| Property | Value |
|----------|-------|
| World name | `technical_cp_track` |
| Actor name | `person_track` |
| Path type | Zigzag (stop-and-turn) |
| Walking speed | ~1 m/s |
| Loop duration | ~30 seconds |
| Delay start | 2 seconds |
| Drone spawn | (0, 0, 0) |
