#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (…/gp2)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SAHTD_ROOT

# Load SAHTD environment (ROS 2, Gazebo, workspaces)
source "$SAHTD_ROOT/env/sahtd_env.sh"

echo "[reset_demo] Publishing reset messages..."

# Reset ByteTrack tracks
ros2 topic pub --once /perception/reset_tracks std_msgs/Empty "{}"

# Reset follower state
ros2 topic pub --once /gp2/follow/reset std_msgs/Empty "{}"

# Reset geo-guard state (if implemented)
ros2 topic pub --once /gp2/guard/reset std_msgs/Empty "{}" || \
  echo "[reset_demo] /gp2/guard/reset not available (skipping)"

echo "[reset_demo] Done."
