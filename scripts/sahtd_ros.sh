#!/usr/bin/env bash
set -e

source "$HOME/gp2/env/sahtd_env.sh"

echo "[sahtd_ros] Launching ROS graph (perception + follow + geo-guard)..."

exec ros2 launch gp2_bringup demo_follow_scene.launch.py
