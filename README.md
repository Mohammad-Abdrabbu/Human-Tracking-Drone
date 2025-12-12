# Security-Aware Human Tracking Drone (SAHTD)

Simulation-first Graduation Project (GP2) – **Security-Aware Human Tracking Drone**  
Single-drone, single-target human tracking with **image-based follower**, **YOLOv8n + ByteTrack**, and **PX4 SITL** in **Gazebo Harmonic**.

---

## 0. Status – Prototype v2 (W1 Follower Freeze)

This repository snapshot corresponds to **Prototype v2**:

- Tag: `prototype_v2` ✓
- Based on tag: `prototype_1` (first full-stack demo)
- Focus here: **W1 slow-walk follower**, with:
  - **Step 0 – Calibrated geometry** from recorded bags.
  - **Step 1 – Three-zone forward controller + altitude hold at 2.5 m.**
- Out of scope (planned but *not* implemented in this freeze):
  - Geometry-aware progressive speed.
  - Explicit NEAR back-off / reverse.
  - Stationary detection rework.
  - Human-aware geo-guard (guarding human + drone).
  - Motion-robust following across speed/direction changes.

This README describes how to run the current prototype and what the environment looks like.

---

## 1. High-Level Overview

SAHTD is a **ROS 2 Humble** + **Gazebo Harmonic** project where a simulated PX4 drone:

1. Streams camera images from **Gazebo**.
2. Runs **YOLOv8n** + **ByteTrack** to detect and track a designated person.
3. Uses an **image-based controller** to follow the person at a calibrated stand-off distance.
4. Exposes controls and status via a **FastAPI backend** and **React/Vite frontend**.

**W1 follower freeze** is tuned for a **slow-walking human** in a simple scene, with:

- Stable calibration: **stand_off_px ≈ 167 px** at “good” distance.
- Explicit **FAR / HOVER / NEAR** zones in front-back motion.
- Simple **altitude hold** targeting ~**2.5 m**.

---

## 2. Stack Overview

Target environment (what this prototype is built and tested on):

- **OS**: Ubuntu 22.04 LTS
- **ROS 2**: Humble Hawksbill (`/opt/ros/humble`)
- **Simulator**: Gazebo Sim 8 (Harmonic)
- **Autopilot**: PX4 SITL (`px4_sitl gz_x500_mono_cam`)
- **Offboard**: MAVSDK (Python)
- **Perception**:
  - YOLOv8n (Ultralytics)
  - ByteTrack MOT → `/perception/tracks` (`vision_msgs/Detection2DArray`)
- **Follower**:
  - `follow_node.py` (Python, MAVSDK)
  - Publishes **body-frame velocity** at ~20 Hz
- **Web stack**:
  - Backend: FastAPI + Uvicorn
  - Frontend: React + Vite

> **Assumption:** Repo is cloned to `~/sahtd`.  
> Scripts and systemd units rely on `SAHTD_ROOT` resolving to this path.

---

## 3. Repository Layout

```text
~/sahtd/                        # SAHTD_ROOT
├── ros2/                       # Main ROS 2 workspace
│   ├── src/
│   │   ├── sahtd_autonomy/     # Perception & Control nodes
│   │   │   └── sahtd_autonomy/
│   │   │       ├── perception/  # YOLO, ByteTrack, viz
│   │   │       ├── control/     # follow_node, geo_guard
│   │   │       └── helpers/     # actor_pose, target_guard, etc.
│   │   └── sahtd_launch/       # Launch files & configs
│   │       ├── launch/
│   │       ├── config/
│   │       └── scenes/
│   ├── build/, install/, log/
├── ros2_bridge/                # Gazebo Harmonic bridge workspace
│   └── src/ros_gz/
├── third_party/
│   └── PX4-Autopilot/          # PX4 SITL repo (x500_mono_cam)
├── web/
│   ├── backend/                # FastAPI backend
│   └── frontend/               # React/Vite operator UI
├── simulation/
│   ├── models/                 # Actor models
│   ├── weights/                # YOLO weights
│   └── worlds/                 # Gazebo world files
├── data/
│   ├── bags/                   # Recorded bag files
│   └── archive/
├── scripts/                    # Organized helper scripts
│   ├── core/                   # start_px4, start_ros, start_web, start_backend
│   ├── sim/                    # spawn_actor, delete_actor
│   ├── data/                   # record_bag, bag_info, analyze_bag
│   ├── debug/                  # debug_tmux, reset_demo
│   └── env/                    # setup_env.sh
├── systemd/                    # User services
│   ├── px4.service, ros.service
│   └── web.service, backend.service
└── docs/                       # Documentation
```

---

## 4. W1 Follower Freeze – Behavior

The follower’s current behavior (Prototype v2) is described by:

### 4.1 Calibrated Geometry (Step 0)
From W1 slow-walk recordings, we measured:
- **stand_off_px ≈ 167 px** → bbox height at comfortable follow distance.
- **max_close_px ≈ 279 px** → typical “too close” upper bound.

These are encoded in `follow.yaml`:
```yaml
stand_off_px: 167.0
max_close_px: 279.0
# eR = stand_off_px - h_f    # distance error in pixel space
```
Where:
- `h_f` = current target bbox height (pixels).
- `eR < 0` means “too close”; `eR > 0` means “too far”.

### 4.2 Three-Zone Controller + Alt Hold (Step 1)
Forward motion is split into three zones:

```yaml
zone_hover_lower_px: 150.0
zone_hover_upper_px: 185.0
zone_near_px:        220.0

zone_hover_yaw_deg:     4.0   # |yaw_error| < 4°
zone_hover_eR_thresh:  20.0   # |eR| < 20 px
alt_hold_enable:      true
alt_hold_m:            2.5    # m
```

Conceptually:
1. **NEAR** (`h_f > zone_near_px = 220`):
   - Too close → no forward push (`vx ≤ 0`).
2. **HOVER** (`150 ≤ h_f ≤ 185`, `|yaw_error| < 4°`, `|eR| < 20 px`):
   - In the sweet spot and well-aligned → `vx = 0` (hover).
3. **FAR** (otherwise):
   - Move forward using a P-controller on `eR = stand_off_px - h_f`.

**Altitude:**
- `alt_hold_enable: true` with `alt_hold_m: 2.5` → follower tries to sit at ~2.5 m while tracking.

The HUD topic (`/sahtd/follow/hud`) prints:
`Z=FAR/HOV/NEAR`, `h_f`, `eR`, `vx`, yaw error, and additional debug info.

---

## 5. Scripts, Globalization & Systemd

### 5.1 SAHTD_ROOT and script behavior
All helper scripts in `scripts/` resolve the repo root automatically:

```bash
# At top of scripts/*.sh
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SAHTD_ROOT
```

Key scripts:
- `scripts/core/start_px4.sh` – start PX4 SITL + Gazebo
- `scripts/core/start_ros.sh` – start ROS graph (bridges, perception, follower)
- `scripts/core/start_backend.sh` – run FastAPI backend
- `scripts/core/start_web.sh` – combined web launcher (backend + frontend)
- `scripts/sim/spawn_actor.sh` / `delete_actor.sh` – manage human actors
- `scripts/data/record_bag.sh` – record bags for analysis
- `scripts/debug/reset_demo.sh` – clean/reset state for a fresh run
- `scripts/debug/debug_tmux.sh` – multi-pane debug session

You can run them from anywhere; they’ll always work relative to `SAHTD_ROOT`.

### 5.2 Systemd units (user services)
User-level services in `systemd/` assume the repo is at `%h/sahtd`:
- `WorkingDirectory=%h/sahtd`
- `Environment=SAHTD_ROOT=%h/sahtd`
- `ExecStart=%h/sahtd/scripts/core/...`

Services:
- `px4.service` – PX4 SITL + Gazebo
- `ros.service` – Bridges + perception + follower nodes
- `web.service` – FastAPI backend + React frontend
- `backend.service` – Backend only

If you clone to a different path than `~/sahtd`, update `SAHTD_ROOT` assumptions in your units and/or scripts accordingly.

---

## 6. Prerequisites (High-Level)

### OS / tools
- **Ubuntu 22.04 LTS**
- `build-essential`, `cmake`, `git`, `curl`, `python3`, `pip`, `tmux` (optional)

### ROS / Gazebo
- **ROS 2 Humble** (`ros-humble-desktop`) + `colcon`
- **Gazebo Sim Harmonic** + ROS 2 bridge:
  - `ros_gz_image`, `ros_gz_bridge` built for Harmonic in `ros2_bridge/`
- ROS packages:
  - `vision_msgs`, `image_transport`, `cv_bridge`, `sensor_msgs`, `geometry_msgs`

### PX4
- `third_party/PX4-Autopilot` checked out on a recent main
- SITL target: `px4_sitl gz_x500_mono_cam`

### Python
- `torch` (CPU build)
- `ultralytics`
- `numpy`
- `opencv-python` (or `python3-opencv` via apt)
- `pillow`
- `mavsdk`
- `fastapi`, `uvicorn`, `PyJWT`, `python-dotenv` (backend)

### Node / Web
- **Node.js** (v22.x tested)
- **npm** (10.x tested)
- Run `npm install` in `web/frontend/` before first use.

---

## 7. Running the W1 Follower Demo (Manual Flow)

Example manual bring-up using separate terminals:

1. **Build & source ROS workspace**
   ```bash
   cd ~/sahtd/ros2
   colcon build --symlink-install
   source install/setup.bash
   ```

2. **Start PX4 SITL + Gazebo (Terminal A)**
   ```bash
   cd ~/sahtd
   ./scripts/core/start_px4.sh
   ```

3. **Start ROS graph (bridges + perception + follower) (Terminal B)**
   ```bash
   cd ~/sahtd/ros2
   ros2 launch sahtd_launch demo_follow.launch.py
   ```

4. **Spawn slow-walk human actor if not auto-spawned (Terminal C)**
   ```bash
   cd ~/sahtd
   ./scripts/sim/spawn_actor.sh slow
   ```

5. **Monitor follower HUD (Terminal D)**
   ```bash
   ros2 topic echo /sahtd/follow/hud
   ```

You should see:
- Mode switching between `Z=FAR`, `Z=HOV`, `Z=NEAR` as the human moves.
- `vx ≈ 0` inside the HOVER band.
- Altitude near ~2.5 m (check in QGroundControl or pose topics).

---

## 8. Versioning & Tags

- **prototype_1** – First full-stack integration:
  - Web backend + frontend
  - Basic bring-up scripts
  - Initial follower + perception

- **prototype_v2** – This W1 follower freeze:
  - **Restructured repository** (ros2/, web/, simulation/, scripts/ subdirs)
  - **Renamed packages** (sahtd_autonomy, sahtd_launch)
  - Globalized scripts + systemd (via `SAHTD_ROOT` / `%h/sahtd`)
  - Calibrated `stand_off_px` / `max_close_px`
  - Three-zone controller (FAR / HOV / NEAR) with alt hold
  - Updated README (this file)

**Future work (not part of this tag):**
- Step 2–5 improvements to follower.
- Lane B (B1–B4) “bulletproof” enhancements.
- Additional scenes, geo-guard UX, and robustness work.

---

## 9. Credits

**University:** University of Petra – Faculty of Information Technology  
**Project:** Security-Aware Human Tracking Drone (SAHTD) – Graduation Project 2

**Team:**
- Mohammad Ramadan Ahmed Abdrabbu
- Abdulrahman Wael Suleiman Thiab
- Fouad Mohammad Ali Omari

**Supervisor:** Dr. Abdelkarem Al-Banna
