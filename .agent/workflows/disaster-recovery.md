---
description: Complete SAHTD workspace recovery after deletion
---

# SAHTD Disaster Recovery Guide

## When to Use This Guide

Use this guide if:
- The entire `~/sahtd` folder was accidentally deleted
- Git repository is corrupted or lost
- ROS2 packages won't build due to missing dependencies
- PX4-Autopilot or ros_gz_bridge is missing

---

## Phase 1: Clone Repository

```bash
cd ~

# Clone from GitHub (use token for private repo)
git clone https://github.com/Mohammad-Abdrabbu/Human-Tracking-Drone.git sahtd
cd sahtd

# Verify clone
git status
git log --oneline -5
```

---

## Phase 2: Restore PX4-Autopilot

PX4-Autopilot is gitignored, must be cloned separately:

```bash
cd ~/sahtd

# Clone PX4-Autopilot to third_party
git clone https://github.com/PX4/PX4-Autopilot.git third_party/PX4-Autopilot
cd third_party/PX4-Autopilot

# Checkout stable version
git checkout v1.14.0

# CRITICAL: Initialize submodules
git submodule update --init --recursive

# Build PX4 SITL
make px4_sitl

cd ~/sahtd
```

---

## Phase 3: Fix mono_cam Sensor Name

The PX4 mono_cam sensor name must be "imager" (not "camera") for ros_gz_bridge:

```bash
# Edit the mono_cam model
nano third_party/PX4-Autopilot/Tools/simulation/gz/models/mono_cam/model.sdf
```

Change line 50 from:
```xml
<sensor name="camera" type="camera">
```
To:
```xml
<sensor name="imager" type="camera">
```

Also set resolution to 640x480 (lines 56-57):
```xml
<width>640</width>
<height>480</height>
```

---

## Phase 4: Restore ros_gz_bridge

ros2_bridge is gitignored, must be cloned separately:

```bash
cd ~/sahtd

# Clone ros_gz for ROS2 Humble
git clone https://github.com/gazebosim/ros_gz.git -b humble ros2_bridge

# Build ros_gz packages
cd ros2_bridge
source /opt/ros/humble/setup.bash
colcon build --symlink-install

cd ~/sahtd
```

---

## Phase 5: Create PX4 Symlink in ros2/src

```bash
cd ~/sahtd

# Create symlink for px4 in ros2/src
ln -sf ../../third_party/PX4-Autopilot ros2/src/px4
```

---

## Phase 6: Build Main Workspace

```bash
cd ~/sahtd

# Source dependencies
source /opt/ros/humble/setup.bash
source ros2_bridge/install/setup.bash

# Build SAHTD packages
colcon build --symlink-install --packages-select sahtd_autonomy sahtd_launch sahtd_web_bridge

# Rebuild ros_gz_interfaces in main workspace (optional, fixes warning)
ln -sf ../../ros2_bridge/ros_gz_interfaces ros2/src/ros_gz_interfaces
colcon build --symlink-install --packages-select ros_gz_interfaces
```

---

## Phase 7: Setup Python Virtual Environments

### Backend venv
```bash
cd ~/sahtd/web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend dependencies
```bash
cd ~/sahtd/web/frontend
npm ci
```

---

## Phase 8: Verify Everything Works

```bash
cd ~/sahtd

# Source workspace
source /opt/ros/humble/setup.bash
source install/setup.bash

# Check ROS packages
ros2 pkg list | grep -E "(sahtd|ros_gz)"

# Run demo
./scripts/demo/demo_committee.sh up --guard on --markers on --events on --spawn --video on
```

---

## Prevention Tips

1. **Never run `rm -rf ~/sahtd`** - Always use `rm -rf ~/sahtd/<specific_folder>`
2. **Commit changes frequently** - Push to GitHub often
3. **Use `git status` before major operations** - Check for uncommitted changes
4. **Backup third_party manually** - PX4-Autopilot takes time to clone

---

## Quick Reference: What's Gitignored

These must be restored manually after clone:
- `third_party/PX4-Autopilot/` - PX4 SITL source
- `ros2_bridge/` - ros_gz packages
- `build/`, `install/`, `log/` - colcon build outputs
- `.venv/` - Python virtual environments
- `node_modules/` - npm packages

---

## Emergency Contacts

- GitHub Repo: https://github.com/Mohammad-Abdrabbu/Human-Tracking-Drone
- PX4-Autopilot: https://github.com/PX4/PX4-Autopilot
- ros_gz: https://github.com/gazebosim/ros_gz
