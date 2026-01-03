#!/bin/bash
# start_ros_fitexpo.sh
set -e

export SAHTD_ROOT=${SAHTD_ROOT:-$HOME/sahtd}

source /opt/ros/humble/setup.bash
source $SAHTD_ROOT/install/setup.bash
source $SAHTD_ROOT/ros2/install/setup.bash

# Point to our custom fence config
FENCE_CONFIG="$SAHTD_ROOT/scripts/fitexpo/geo_guard_fitexpo.yaml"

echo "Starting ROS nodes for Fit Expo..."
echo "Using fence config: $FENCE_CONFIG"

# We launch the standard launch file but override parameters
ros2 launch sahtd_launch demo_follow.launch.py \
    fence_config:=$FENCE_CONFIG
