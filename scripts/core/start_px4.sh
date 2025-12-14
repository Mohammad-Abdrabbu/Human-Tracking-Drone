#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (scripts/core/start_px4.sh → ../..)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

source "$SAHTD_ROOT/scripts/env/setup_env.sh"

# World selection: defaults to "default", can be overridden via PX4_GZ_WORLD env var
# Example: PX4_GZ_WORLD=technical_cp_track ./scripts/core/start_px4.sh
GZ_WORLD="${PX4_GZ_WORLD:-default}"

echo "[sahtd_px4] Starting PX4 SITL + Gazebo Harmonic..."
echo "[sahtd_px4] World: $GZ_WORLD"

PX4_DIR="$SAHTD_ROOT/third_party/PX4-Autopilot"
cd "$PX4_DIR"

# Build PX4 SITL if not already built
make px4_sitl

# Set GZ_SIM_RESOURCE_PATH for model:// URI resolution (actors, meshes)
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+$GZ_SIM_RESOURCE_PATH:}$SAHTD_ROOT/simulation/models"
echo "[sahtd_px4] GZ_SIM_RESOURCE_PATH: $GZ_SIM_RESOURCE_PATH"

# Start PX4 SITL with Gazebo Harmonic (x500_mono_cam)
# Using environment variables instead of make target (Gazebo Harmonic method)
# PX4_SYS_AUTOSTART: 4010 = x500_mono_cam (forward-facing camera)
# PX4_GZ_WORLD: world SDF name (without .sdf extension)
exec env PX4_SYS_AUTOSTART=4010 PX4_GZ_MODEL_POSE="0,0,0.05" PX4_GZ_MODEL=x500_mono_cam PX4_GZ_WORLD="$GZ_WORLD" ./build/px4_sitl_default/bin/px4

