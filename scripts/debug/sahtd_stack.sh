#!/usr/bin/env bash
# scripts/debug/sahtd_stack.sh
# SAHTD Stack Launcher - Runs PX4 and ROS in tmux for development

set -e

SESSION_NAME="sahtd_stack"

# Resolve SAHTD_ROOT
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

# Kill existing session if running
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

echo "Starting SAHTD Stack session..."

# Create new session (detached)
tmux new-session -d -s $SESSION_NAME -n "stack"

# === LAYOUT: 2 panes (top/bottom split) ===
# Top: PX4 output
# Bottom: ROS output

tmux split-window -v -t $SESSION_NAME

# === Top Pane: PX4 SITL ===
tmux select-pane -t 0
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Starting PX4 SITL + Gazebo ===' && sleep 1" C-m
tmux send-keys -t $SESSION_NAME "$SAHTD_ROOT/scripts/core/start_px4.sh" C-m

# === Bottom Pane: ROS Launch ===
tmux select-pane -t 1
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Waiting 15s for PX4/Gazebo startup ===' && sleep 15" C-m
tmux send-keys -t $SESSION_NAME "echo '=== Starting ROS Stack ===' && sleep 1" C-m
tmux send-keys -t $SESSION_NAME "$SAHTD_ROOT/scripts/core/start_ros.sh" C-m

# Adjust pane sizes (60/40 split)
tmux resize-pane -t 0 -y 30
tmux resize-pane -t 1 -y 20

# Attach to session
echo ""
echo "==================================================="
echo "SAHTD Stack session started!"
echo "  - Top pane: PX4 SITL + Gazebo"
echo "  - Bottom pane: ROS perception + control"
echo ""
echo "Controls:"
echo "  Ctrl+b, arrow keys - switch panes"
echo "  Ctrl+b, [ - scroll mode (q to exit)"
echo "  Ctrl+b, d - detach (keeps running)"
echo "  Ctrl+c in panes - stop services"
echo ""
echo "To reattach: tmux attach -t $SESSION_NAME"
echo "To kill: tmux kill-session -t $SESSION_NAME"
echo "==================================================="
echo ""

tmux attach -t $SESSION_NAME
