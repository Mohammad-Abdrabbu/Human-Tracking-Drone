#!/usr/bin/env bash
set -e

source "$HOME/gp2/env/sahtd_env.sh"

echo "[sahtd_px4] Starting PX4 SITL + Gazebo..."

PX4_DIR="$HOME/gp2/third_party/PX4-Autopilot"
cd "$PX4_DIR"

# Start PX4 SITL with Gazebo Harmonic (x500_mono_cam)
exec make px4_sitl gz_x500_mono_cam
