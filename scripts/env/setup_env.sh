#!/usr/bin/env bash

##
# SAHTD unified environment for services & manual sessions
# - ROS 2 Humble
# - Gazebo Harmonic (gz-sim8)
# - GP2 workspaces
# - PX4 worlds + custom models
##

# Stop on errors (useful for systemd; failing fast is better than half-broken env)
set -e

############################
# Base directories
############################

# Root project folder
# Resolve SAHTD_ROOT relative to this script (env/sahtd_env.sh -> ..)
ENV_SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export SAHTD_ROOT="$(cd "$ENV_SCRIPT_DIR/../.." && pwd)"

# ROS workspaces
export SAHTD_WS_ROS="$SAHTD_ROOT/ros2"
export SAHTD_WS_BRIDGE="$SAHTD_ROOT/ros2_bridge"

# PX4 source tree
export SAHTD_PX4_ROOT="$SAHTD_ROOT/third_party/PX4-Autopilot"

############################
# ROS 2 + workspaces
############################

# Core ROS 2 (Humble)
if [ -f "/opt/ros/humble/setup.bash" ]; then
  # shellcheck source=/opt/ros/humble/setup.bash
  source /opt/ros/humble/setup.bash
else
  echo "[SAHTD_ENV] WARNING: /opt/ros/humble/setup.bash not found." >&2
fi

# ros_gz Harmonic bridge workspace (if built)
if [ -f "$SAHTD_WS_BRIDGE/install/setup.bash" ]; then
  # shellcheck source=/dev/null
  source "$SAHTD_WS_BRIDGE/install/setup.bash"
else
  echo "[SAHTD_ENV] NOTE: ros2_bridge not found or not built yet: $SAHTD_WS_BRIDGE" >&2
fi

# Main GP2 workspace
if [ -f "$SAHTD_WS_ROS/install/setup.bash" ]; then
  # shellcheck source=/dev/null
  source "$SAHTD_WS_ROS/install/setup.bash"
else
  echo "[SAHTD_ENV] WARNING: ros2 not found or not built yet: $SAHTD_WS_ROS" >&2
fi

############################
# DDS / ROS options
############################

# Use a fixed ROS 2 domain so PX4 <-> ROS work consistently
export ROS_DOMAIN_ID=0

# Nicer colored logs (also visible in terminals)
export RCUTILS_COLORIZED_OUTPUT=1

# Optional: force Fast DDS explicitly (you've been using the default; leave commented unless needed)
# export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

############################
# Gazebo Harmonic paths
############################

# Gazebo  Harmonic (gz-sim8) resources:
# - PX4 worlds
# - Your custom actor models, etc.
PX4_GZ_WORLDS="$SAHTD_PX4_ROOT/Tools/simulation/gz/worlds"
SAHTD_MODELS="$SAHTD_ROOT/simulation/models"

# Prepend SAHTD paths while preserving any existing value
if [ -z "${GZ_SIM_RESOURCE_PATH:-}" ]; then
  export GZ_SIM_RESOURCE_PATH="$SAHTD_MODELS:$PX4_GZ_WORLDS"
else
  export GZ_SIM_RESOURCE_PATH="$SAHTD_MODELS:$PX4_GZ_WORLDS:$GZ_SIM_RESOURCE_PATH"
fi

############################
# Marker
############################

export SAHTD_ENV_LOADED=1
# You can uncomment this during debugging if you want a visible confirmation:
# echo "[SAHTD_ENV] Environment loaded (SAHTD_ROOT=$SAHTD_ROOT)"
