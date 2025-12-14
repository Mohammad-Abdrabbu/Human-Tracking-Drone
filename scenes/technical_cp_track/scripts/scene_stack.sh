#!/usr/bin/env bash
# scenes/technical_cp_track/scripts/scene_stack.sh
# Scene 1 Stack Launcher - Track Demo (PX4 + ROS in tmux)

set -e

SESSION_NAME="scene_track"

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"
export SAHTD_ROOT

# Kill existing session if running
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

echo "Starting Scene 1 (Track) Stack..."

# Create new session (detached)
tmux new-session -d -s $SESSION_NAME -n "stack"

# === LAYOUT: 2 panes (top/bottom split) ===
tmux split-window -v -t $SESSION_NAME

# === Top Pane: PX4 SITL ===
tmux select-pane -t 0
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Scene 1: Track Demo - PX4 ===' && sleep 1" C-m
tmux send-keys -t $SESSION_NAME "PX4_GZ_WORLD=technical_cp_track $SAHTD_ROOT/scripts/core/start_px4.sh" C-m

# === Bottom Pane: ROS Launch ===
tmux select-pane -t 1
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Waiting 15s for PX4/Gazebo ===' && sleep 15" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Starting ROS (geofence DISABLED) ==='" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch sahtd_launch demo_follow.launch.py world_name:=technical_cp_track enable_geofence:=false" C-m

# Adjust pane sizes
tmux resize-pane -t 0 -y 30
tmux resize-pane -t 1 -y 20

# Attach
cat << 'EOF'
===================================================
Scene 1 (Track Demo) Stack Started!
  - Top pane: PX4 SITL + Gazebo
  - Bottom pane: ROS (geofence OFF)

Controls:
  Ctrl+b, arrow keys - switch panes
  Ctrl+b, [ - scroll mode (q to exit)
  Ctrl+b, d - detach (keeps running)

To reattach: tmux attach -t scene_track
To kill: tmux kill-session -t scene_track
===================================================
EOF

tmux attach -t $SESSION_NAME
