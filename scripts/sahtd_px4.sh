#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (…/gp2)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SAHTD_ROOT

source "$SAHTD_ROOT/env/sahtd_env.sh"

echo "[sahtd_px4] Starting PX4 SITL + Gazebo..."

PX4_DIR="$SAHTD_ROOT/third_party/PX4-Autopilot"
cd "$PX4_DIR"

# Start PX4 SITL with Gazebo Harmonic (x500_mono_cam)
exec make px4_sitl gz_x500_mono_cam
