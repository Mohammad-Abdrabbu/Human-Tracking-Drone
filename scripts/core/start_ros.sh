#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (scripts/core/start_ros.sh → ../..)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

source "$SAHTD_ROOT/scripts/env/setup_env.sh"

echo "[sahtd_ros] Launching ROS graph (perception + follow + geo-guard)..."

exec ros2 launch sahtd_launch demo_follow.launch.py
