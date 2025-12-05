#!/usr/bin/env bash
set -e

# Load SAHTD environment (ROS 2, Gazebo, workspaces)
source "$HOME/gp2/env/sahtd_env.sh"

echo "[reset_demo] Publishing reset messages..."

# Reset ByteTrack tracks
ros2 topic pub --once /perception/reset_tracks std_msgs/Empty "{}"

# Reset follower state
ros2 topic pub --once /gp2/follow/reset std_msgs/Empty "{}"

# Reset geo-guard state (if implemented)
ros2 topic pub --once /gp2/guard/reset std_msgs/Empty "{}" || \
  echo "[reset_demo] /gp2/guard/reset not available (skipping)"

echo "[reset_demo] Done."
