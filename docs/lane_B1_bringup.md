# Lane B1 – Debug Bring-up & Observability Manual

## 1. Purpose and Scope

**Lane B1** provides a repeatable, consistent debug bring-up mode for the SAHTD (Security-Aware Human Tracking Drone) system. It is designed specifically for **development and troubleshooting** of the follower, geo-guard, and perception components.

### What Lane B1 Does

- Launches the full SAHTD stack (PX4 + Gazebo + ROS2 nodes) in a structured tmux session
- Provides real-time visibility into key ROS topics through dedicated introspection panes
- Enables rapid debugging by showing follower state, geo-guard status, and perception performance side-by-side
- Maintains idempotency: safe to run multiple times without creating duplicate sessions

### What Lane B1 Does NOT Do

- **Not for production deployment** – use systemd services (`sahtd-*.service`) for production
- **Not a replacement for existing workflows** – sahtd_px4.sh, sahtd_ros.sh, and systemd services remain unchanged
- **Does not include the backend** – FastAPI backend can be run separately if needed

---

## 2. How to Run Lane B1 Debug Mode

### Prerequisites

1. **tmux installed:**
   ```bash
   sudo apt install tmux
   ```

2. **GP2 workspace built:**
   ```bash
   cd ~/gp2/ws/gp2_ws
   colcon build
   ```

3. **Environment script exists:**
   - `~/gp2/env/sahtd_env.sh` must be present and functional

### Starting the Debug Session

From a fresh terminal:

```bash
cd ~/gp2
./scripts/sahtd_debug_tmux.sh
```

**First-time setup only:**
```bash
chmod +x scripts/sahtd_debug_tmux.sh
```

### What Happens

1. Script checks if `sahtd_debug` session exists
   - If exists: attaches to existing session
   - If not: creates new session with 6 panes
2. Pane 0 starts PX4 + Gazebo (takes ~10-15 seconds)
3. Pane 1 waits 10s for PX4 to stabilize, then starts ROS2 graph
4. Panes 2-5 wait 15s, then start topic monitors
5. You are automatically attached to the session

### Tmux Commands

| Action | Command |
|--------|---------|
| **Detach from session** | `Ctrl+B` then `D` |
| **Reattach to session** | `tmux attach-session -t sahtd_debug` |
| **Kill session completely** | `tmux kill-session -t sahtd_debug` |
| **Navigate between panes** | `Ctrl+B` then arrow keys |
| **Scroll in a pane** | `Ctrl+B` then `[`, then use arrow keys or PgUp/PgDn, press `q` to exit scroll mode |

### Stopping the Debug Session

**Option 1: Kill the entire session (recommended)**
```bash
tmux kill-session -t sahtd_debug
```

**Option 2: Stop processes manually**
- In Pane 0 (PX4): `Ctrl+C`
- In Pane 1 (ROS2): `Ctrl+C`
- Then kill the session: `tmux kill-session -t sahtd_debug`

---

## 3. Pane/Window Mapping

The `sahtd_debug` session consists of 6 panes arranged as follows:

```
┌────────────────────┬────────────────────┐
│  Pane 0            │  Pane 1            │
│  PX4+Gazebo        │  ROS2-Graph        │
│                    │                    │
├────────────────────┼────────────────────┤
│  Pane 4            │  Pane 2            │
│  Perception-Hz     │  Follow-HUD        │
├────────────────────┼────────────────────┤
│  Pane 5            │  Pane 3            │
│  Seen-IDs          │  Guard-Status      │
└────────────────────┴────────────────────┘
```

### Pane 0: PX4 + Gazebo

- **Command:** `./scripts/sahtd_px4.sh`
- **Purpose:** Runs PX4 SITL + Gazebo Harmonic with x500_mono_cam vehicle
- **Expected output:**
  - PX4 initialization logs
  - Gazebo GUI window appears
  - World loads with drone visible
  - No crash messages

**What to look for:**
- ✅ `INFO  [gazebo_mavlink_interface] Gazebo connected` (PX4 ↔ Gazebo link established)
- ✅ Gazebo GUI is responsive
- ❌ `Segmentation fault` or `Gazebo crashed` (indicates GPU/driver issues)

---

### Pane 1: ROS2 Graph

- **Command:** `./scripts/sahtd_ros.sh`
- **Purpose:** Launches all ROS2 nodes via `demo_follow_scene.launch.py`
- **Expected output:**
  - 5 nodes start in sequence:
    1. `camera_bridge` – bridges Gazebo camera to `/camera/image_raw`
    2. `yolo_node` – YOLOv8 person detection
    3. `bytetrack_node` – multi-object tracking
    4. `geo_guard_node` – geo-fence enforcement
    5. `follow_node` – visual servoing + MAVSDK control
  - All nodes print initialization messages
  - No `ERROR` or `FATAL` logs

**What to look for:**
- ✅ `[yolo_node]: YOLOv8 ready (conf=0.25, imgsz=416)`
- ✅ `[bytetrack_node]: ByteTrack: initialized`
- ✅ `[geo_guard_node]: GEOGUARD cfg → frame=map(ENU), vertices=...`
- ✅ `[follow_node]: Connecting MAVSDK @ udpin://0.0.0.0:14540`
- ✅ `[follow_node]: Ready for takeoff`
- ❌ Any `ERROR` or node crashes

---

### Pane 2: Follow HUD

- **Command:** `ros2 topic echo /gp2/follow/hud`
- **Purpose:** Monitor follower state and behavior in real-time
- **Expected output (when working):**
  - Before takeoff: `GROUND` state messages
  - After takeoff: `SEARCH` or `LOCKED` state messages
  - Example: `data: 'LOCKED: id=17 cx=640.2 h=245.8'`

**What to look for:**
- ✅ Messages appearing at ~1-20 Hz (depends on follower state)
- ✅ State transitions: `GROUND` → `TAKEOFF` → `SEARCH` → `LOCKED`
- ✅ When target selected: shows target ID, center x, height
- ❌ No messages for >5 seconds (follower may be stuck or not running)
- ❌ Continuous `ERROR` messages

---

### Pane 3: Guard Status

- **Command:** `ros2 topic echo /gp2/guard/status`
- **Purpose:** Monitor geo-fence status
- **Expected output (when working):**
  - Most of the time: `data: 'NORMAL'`
  - When near fence (within soft margin): `data: 'GEOGUARD_HOLD'`
  - When inside hard margin (if enabled): `data: 'GEOGUARD_VIOLATION'`

**What to look for:**
- ✅ Initial message: `NORMAL`
- ✅ Status updates at ~10-20 Hz when drone is moving
- ✅ State changes when drone approaches fence edges
- ❌ No messages appearing (geo_guard_node not running or pose not published)
- ❌ Stuck in `VIOLATION` when drone is far from fence (algorithm error)

---

### Pane 4: Perception Hz

- **Command:** `ros2 topic hz /perception/tracks`
- **Purpose:** Monitor perception pipeline performance (detections → tracking)
- **Expected output (when working):**
  - When human is visible: `average rate: 10.0-20.0 Hz`
  - When no human visible: rate may drop or show `no new messages`

**What to look for:**
- ✅ Nonzero Hz when human actor is in camera view
- ✅ Stable rate (10-20 Hz typical for YOLOv8n + ByteTrack)
- ⚠️ Rate drops below 5 Hz → ByteTrack may switch to degraded mode (see diagnostics)
- ❌ `WARNING: no new messages` for extended period when human should be visible
- ❌ Rate = 0 Hz (perception pipeline broken)

---

### Pane 5: Seen Track IDs

- **Command:** `ros2 topic echo /gp2/follow/seen_ids`
- **Purpose:** Monitor which track IDs the follower can see
- **Expected output (when working):**
  - When no humans visible: `data: ''` or `data: 'ids='`
  - When humans visible: `data: 'ids=17,23,45'` (comma-separated track IDs)

**What to look for:**
- ✅ Messages update at ~10-20 Hz
- ✅ IDs appear when human is in camera view
- ✅ IDs persist across frames (indicates stable tracking)
- ❌ IDs constantly changing (tracking instability)
- ❌ No IDs when human is clearly visible (detection or tracking failure)

---

## 4. How to Test Lane B1 is Working

### Test 1: Basic Bring-up (Smoke Test)

**Purpose:** Verify all components start successfully and topics are publishing.

**Steps:**

1. Start the debug session:
   ```bash
   cd ~/gp2
   ./scripts/sahtd_debug_tmux.sh
   ```

2. Wait 30 seconds for full initialization:
   - Gazebo GUI should appear
   - All 6 panes should show activity

3. Check each pane systematically:

   **Pane 0 (PX4+Gazebo):**
   - ✅ Gazebo GUI is open and responsive
   - ✅ x500 drone is visible in the world
   - ✅ No crash messages in the pane

   **Pane 1 (ROS2-Graph):**
   - ✅ All 5 nodes started without errors
   - ✅ See "Ready for takeoff" or similar from follow_node

   **Pane 2 (Follow-HUD):**
   - ✅ Messages appearing (even if just `GROUND` state)
   - ✅ No continuous ERROR logs

   **Pane 3 (Guard-Status):**
   - ✅ Initial `NORMAL` status published
   - ✅ Messages updating periodically

   **Pane 4 (Perception-Hz):**
   - ✅ Topic exists (may show 0 Hz if no human in view)
   - ⚠️ If human is in default world spawn, should show nonzero Hz

   **Pane 5 (Seen-IDs):**
   - ✅ Messages appearing (may be empty if no detections)

4. **Pass Criteria:**
   - All panes are active (no crashes)
   - Topics exist and are publishing
   - No ERROR or FATAL messages in ROS2 graph pane
   - Gazebo is responsive

5. **Fail Criteria:**
   - Any pane crashed or frozen
   - ROS2 nodes failed to start
   - Topics don't exist after 30 seconds
   - Gazebo segfaulted

**Expected Time:** 1-2 minutes

---

### Test 2: Geo-guard Interaction (Functional Check)

**Purpose:** Verify geo-guard actually monitors position and changes state near fence.

**Prerequisites:** Test 1 passed.

**Steps:**

1. While still in the debug session, identify the geo-fence vertices:
   - In Pane 1 (ROS2-Graph), look for geo_guard_node initialization log:
     ```
     GEOGUARD cfg → frame=map(ENU), vertices=N, soft=0.80m, hard=0.00m, ...
     ```
   - Note the bounding box (e.g., `x:[-5.0, 5.0] y:[-5.0, 5.0]`)

2. Spawn a human actor in Gazebo (if not already present):
   - Use existing Gazebo commands or GUI to add a walking human
   - Alternatively, use PX4 SITL console (if available) or skip this step

3. Command the drone to takeoff (via MAVSDK or PX4 console):
   - Option A: Use follow_node's built-in takeoff (if target is visible and selected)
   - Option B: Manual PX4 command: `commander takeoff`

4. Move the drone (or human) close to one of the fence edges:
   - If fence is at `x:[−5, 5], y:[−5, 5]`, move drone to `x=4.5, y=0` (within soft margin)
   - This can be done via PX4 console position commands or by having the follower track a human near the edge

5. **Observe Pane 3 (Guard-Status):**
   - ✅ Status should change from `NORMAL` to `GEOGUARD_HOLD` when within soft margin (0.8m default)
   - ✅ Reason topic (visible in ROS2 graph logs) should show `edge=X.XXm`

6. **Observe Pane 2 (Follow-HUD):**
   - ✅ Follower should still be operational but may show modified velocity commands
   - ✅ State machine should remain coherent (not crash)

7. Move drone back away from the fence:
   - ✅ Guard status should return to `NORMAL` after debounce delay (~300ms)

**Pass Criteria:**
- Guard status transitions from `NORMAL` → `HOLD` → `NORMAL` based on drone position
- No crashes in any pane
- Follower continues to operate (HUD still publishing)

**Fail Criteria:**
- Guard status stuck at `NORMAL` even when near fence (geo-guard not working)
- Guard status stuck at `HOLD` when far from fence (algorithm bug)
- Follower crashes when guard activates

**Expected Time:** 3-5 minutes

**Note:** This test requires manual control or a human actor walking near the fence. If you don't have a human actor configured, you can skip this test or manually command the drone via PX4 console.

---

## 5. Notes and Troubleshooting

### General Issues

**Problem: `tmux: command not found`**

**Solution:**
```bash
sudo apt install tmux
```

---

**Problem: Topics don't appear in introspection panes**

**Possible causes:**
1. ROS2 environment not sourced correctly
   - Check Pane 1 for sourcing errors
   - Manually verify: `cd ~/gp2 && source env/sahtd_env.sh && ros2 topic list`

2. Nodes haven't started yet
   - Wait 15-30 seconds after ROS2 graph starts
   - Check Pane 1 for node startup messages

3. Nodes crashed during initialization
   - Check Pane 1 for ERROR messages
   - Common issue: YOLO weights not found → check `/home/ramadan/gp2/assets/weights/yolov8n.pt` exists

**Solution:**
- Kill session: `tmux kill-session -t sahtd_debug`
- Review logs manually by running scripts individually
- Fix underlying issue (missing weights, workspace not built, etc.)
- Retry debug script

---

**Problem: Gazebo crashes or segfaults**

**Possible causes:**
- GPU driver issues
- Insufficient GPU memory
- Gazebo Harmonic installation corrupted

**Solution:**
1. Check GPU drivers are up to date:
   ```bash
   nvidia-smi  # for NVIDIA GPUs
   ```
2. Try software rendering (slower):
   ```bash
   export LIBGL_ALWAYS_SOFTWARE=1
   ./scripts/sahtd_debug_tmux.sh
   ```
3. Verify Gazebo Harmonic installation:
   ```bash
   gz sim --version
   ```

---

**Problem: PX4 won't connect to MAVSDK (follow_node)**

**Possible causes:**
- PX4 SITL didn't start properly
- Port conflict on 14540
- MAVSDK version mismatch

**Solution:**
1. Check Pane 0 for PX4 SITL errors
2. Verify port 14540 is not already in use:
   ```bash
   sudo netstat -tulpn | grep 14540
   ```
3. Kill any stale PX4 processes:
   ```bash
   killall px4
   killall gz
   ```
4. Restart debug session

---

**Problem: Perception Hz is 0 even with human visible**

**Possible causes:**
1. Camera bridge not working → no images on `/camera/image_raw`
2. YOLO node crashed or not detecting
3. ByteTrack node crashed

**Solution:**
1. Check camera topic:
   ```bash
   ros2 topic hz /camera/image_raw
   ```
   - Should show ~30 Hz if camera is working
   - If 0 Hz: camera bridge failed (check Gazebo topic name in launch file)

2. Check detections:
   ```bash
   ros2 topic hz /perception/detections
   ```
   - Should show ~10-20 Hz when human visible
   - If 0 Hz: YOLO not detecting (check model path, confidence threshold)

3. Review Pane 1 logs for yolo_node and bytetrack_node errors

---

**Problem: Geo-guard always shows NORMAL, even near fence**

**Possible causes:**
1. Drone position not being published to `/gp2/vehicle/pose_local`
2. Fence vertices misconfigured
3. Geo-guard node not running

**Solution:**
1. Check pose topic:
   ```bash
   ros2 topic echo /gp2/vehicle/pose_local --once
   ```
   - Should show current drone position in ENU frame
   - If no messages: follow_node not publishing pose (MAVSDK connection issue)

2. Check fence config in `gp2_bringup/config/geo_guard_params.yaml`:
   - Verify `vertices` parameter is set correctly
   - Verify `soft_margin_m` is reasonable (default: 0.8m)

3. Check Pane 1 for geo_guard_node startup logs

---

### Advanced Tips

**Customize tmux layout:**
- After session starts, you can resize panes with `Ctrl+B` then `Alt+Arrow Keys`
- Save custom layout for future sessions (requires tmux config edits)

**Add bag recording:**
- In a new terminal (outside tmux):
  ```bash
  cd ~/gp2
  source env/sahtd_env.sh
  ros2 bag record /perception/tracks /gp2/follow/cmd_body /gp2/guard/status -o debug_session
  ```

**Monitor additional topics:**
- Detach from session (`Ctrl+B` then `D`)
- In a separate terminal:
  ```bash
  source ~/gp2/env/sahtd_env.sh
  ros2 topic echo /gp2/guard/reason
  ros2 topic echo /perception/diagnostics
  ```

---

## 6. Quick Reference

### One-Command Start
```bash
cd ~/gp2 && ./scripts/sahtd_debug_tmux.sh
```

### One-Command Stop
```bash
tmux kill-session -t sahtd_debug
```

### Pane Quick Check
| Pane | Look For | Good Sign | Bad Sign |
|------|----------|-----------|----------|
| 0 | Gazebo GUI | Window visible, no crashes | Segfault, frozen |
| 1 | ROS2 logs | All 5 nodes started | ERROR/FATAL messages |
| 2 | Follow HUD | State messages | No messages or continuous errors |
| 3 | Guard status | `NORMAL` → `HOLD` transitions | No messages or stuck |
| 4 | Perception Hz | 10-20 Hz with human visible | 0 Hz or `WARNING: no new messages` |
| 5 | Seen IDs | Track IDs when human visible | No IDs or constantly changing |

### Related Documentation
- **System Overview:** `system_overview.md` (artifact)
- **Lane S Scripts:** `~/gp2/scripts/sahtd_px4.sh`, `sahtd_ros.sh`
- **Systemd Services:** `~/gp2/systemd/*.service`
- **Launch File:** `~/gp2/ws/gp2_ws/src/gp2_bringup/launch/demo_follow_scene.launch.py`
