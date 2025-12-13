#!/usr/bin/env bash
# scripts/debug/reset_demo.sh
# Stop all SAHTD services, kill processes, and clean up tmux sessions

set -e

# Resolve SAHTD_ROOT
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================"
echo "SAHTD Demo Reset"
echo "============================================"
echo ""

# Kill tmux sessions
echo "[1/4] Stopping tmux sessions..."
tmux kill-session -t sahtd_stack 2>/dev/null && echo "  ✓ Killed sahtd_stack session" || echo "  - sahtd_stack not running"
tmux kill-session -t sahtd_introspect 2>/dev/null && echo "  ✓ Killed sahtd_introspect session" || echo "  - sahtd_introspect not running"
tmux kill-session -t sahtd_debug 2>/dev/null && echo "  ✓ Killed sahtd_debug session (old)" || echo "  - sahtd_debug not running"
echo ""

# Stop systemd services (if running)
echo "[2/4] Stopping systemd services..."
systemctl --user stop px4 2>/dev/null && echo "  ✓ Stopped px4 service" || echo "  - px4 service not active"
systemctl --user stop ros 2>/dev/null && echo "  ✓ Stopped ros service" || echo "  - ros service not active"
systemctl --user stop backend 2>/dev/null && echo "  ✓ Stopped backend service" || echo "  - backend service not active"
systemctl --user stop web 2>/dev/null && echo "  ✓ Stopped web service" || echo "  - web service not active"
echo ""

# Kill processes forcefully
echo "[3/4] Killing remaining processes..."
killall -9 gz 2>/dev/null && echo "  ✓ Killed Gazebo" || echo "  - Gazebo not running"
killall -9 px4 2>/dev/null && echo "  ✓ Killed PX4" || echo "  - PX4 not running"
killall -9 ruby 2>/dev/null && echo "  ✓ Killed Ruby (Gazebo server)" || echo "  - Ruby not running"
killall -9 gzserver 2>/dev/null && echo "  ✓ Killed gzserver" || echo "  - gzserver not running"
killall -9 gzclient 2>/dev/null && echo "  ✓ Killed gzclient" || echo "  - gzclient not running"
# Note: Not killing python3 globally as it might kill other important processes
echo ""

# Clean ROS daemon
echo "[4/4] Restarting ROS daemon..."
ros2 daemon stop 2>/dev/null && sleep 1
ros2 daemon start 2>/dev/null && echo "  ✓ ROS daemon restarted" || echo "  - ROS daemon restart failed (might not be sourced)"
echo ""

echo "============================================"
echo "Reset complete!"
echo ""
echo "System is now clean. You can start fresh with:"
echo "  ~/sahtd/scripts/debug/sahtd_stack.sh"
echo "  ~/sahtd/scripts/debug/sahtd_introspect.sh"
echo "============================================"
