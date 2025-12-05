#!/usr/bin/env bash

##
# Lane B1 Debug Bring-up
# =====================
# Creates a tmux session with SAHTD stack + introspection panes for debugging
# follower/geo-guard/perception behavior.
#
# Pane Layout (6 panes):
#   Pane 0: PX4 + Gazebo (sahtd_px4.sh)
#   Pane 1: ROS2 graph (sahtd_ros.sh) - camera + YOLO + ByteTrack + follow + geo-guard
#   Pane 2: Follow HUD monitor (ros2 topic echo /gp2/follow/hud)
#   Pane 3: Geo-guard status (ros2 topic echo /gp2/guard/status)
#   Pane 4: Perception rate check (ros2 topic hz /perception/tracks)
#   Pane 5: Seen IDs monitor (ros2 topic echo /gp2/follow/seen_ids)
#
# Usage:
#   ./scripts/sahtd_debug_tmux.sh
#
# To detach: Ctrl+B then D
# To reattach: tmux attach-session -t sahtd_debug
# To kill session: tmux kill-session -t sahtd_debug
##

set -e

SESSION="sahtd_debug"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GP2_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Install with: sudo apt install tmux"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already exists. Attaching..."
    exec tmux attach-session -t "$SESSION"
fi

echo "Creating new tmux session '$SESSION' for Lane B1 debug..."

# Source environment (we'll do this in each pane)
ENV_SCRIPT="$GP2_ROOT/env/sahtd_env.sh"
if [ ! -f "$ENV_SCRIPT" ]; then
    echo "Error: Environment script not found: $ENV_SCRIPT"
    exit 1
fi

# Create new session with first pane (PX4 + Gazebo)
tmux new-session -d -s "$SESSION" -n "SAHTD-Debug"

# Pane 0: PX4 + Gazebo
tmux send-keys -t "$SESSION:0.0" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.0" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.0" "echo '=== Lane B1: Starting PX4 + Gazebo ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.0" "./scripts/sahtd_px4.sh" C-m

# Split horizontally for pane 1
tmux split-window -h -t "$SESSION:0"

# Pane 1: ROS2 graph
tmux send-keys -t "$SESSION:0.1" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.1" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.1" "echo '=== Lane B1: Waiting 10s for PX4/Gazebo to stabilize ===' && sleep 10" C-m
tmux send-keys -t "$SESSION:0.1" "echo '=== Lane B1: Starting ROS2 graph ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.1" "./scripts/sahtd_ros.sh" C-m

# Split pane 1 vertically for pane 2
tmux select-pane -t "$SESSION:0.1"
tmux split-window -v -t "$SESSION:0.1"

# Pane 2: Follow HUD monitor
tmux send-keys -t "$SESSION:0.2" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.2" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.2" "echo '=== Lane B1: Follow HUD Monitor ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.2" "echo 'Waiting for follow_node to start...' && sleep 15" C-m
tmux send-keys -t "$SESSION:0.2" "ros2 topic echo /gp2/follow/hud" C-m

# Split pane 2 horizontally for pane 3
tmux select-pane -t "$SESSION:0.2"
tmux split-window -h -t "$SESSION:0.2"

# Pane 3: Geo-guard status
tmux send-keys -t "$SESSION:0.3" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.3" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.3" "echo '=== Lane B1: Geo-guard Status Monitor ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.3" "echo 'Waiting for geo_guard_node to start...' && sleep 15" C-m
tmux send-keys -t "$SESSION:0.3" "ros2 topic echo /gp2/guard/status" C-m

# Split pane 0 vertically for pane 4
tmux select-pane -t "$SESSION:0.0"
tmux split-window -v -t "$SESSION:0.0"

# Pane 4: Perception rate check
tmux send-keys -t "$SESSION:0.4" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.4" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.4" "echo '=== Lane B1: Perception Rate Monitor ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.4" "echo 'Waiting for perception nodes to start...' && sleep 15" C-m
tmux send-keys -t "$SESSION:0.4" "ros2 topic hz /perception/tracks" C-m

# Split pane 4 horizontally for pane 5
tmux select-pane -t "$SESSION:0.4"
tmux split-window -h -t "$SESSION:0.4"

# Pane 5: Seen IDs monitor
tmux send-keys -t "$SESSION:0.5" "cd $GP2_ROOT" C-m
tmux send-keys -t "$SESSION:0.5" "source $ENV_SCRIPT" C-m
tmux send-keys -t "$SESSION:0.5" "echo '=== Lane B1: Seen Track IDs Monitor ===' && sleep 1" C-m
tmux send-keys -t "$SESSION:0.5" "echo 'Waiting for bytetrack_node to start...' && sleep 15" C-m
tmux send-keys -t "$SESSION:0.5" "ros2 topic echo /gp2/follow/seen_ids" C-m

# Set pane titles for clarity
tmux select-pane -t "$SESSION:0.0" -T "PX4+Gazebo"
tmux select-pane -t "$SESSION:0.1" -T "ROS2-Graph"
tmux select-pane -t "$SESSION:0.2" -T "Follow-HUD"
tmux select-pane -t "$SESSION:0.3" -T "Guard-Status"
tmux select-pane -t "$SESSION:0.4" -T "Perception-Hz"
tmux select-pane -t "$SESSION:0.5" -T "Seen-IDs"

# Select the ROS2 graph pane as default focus
tmux select-pane -t "$SESSION:0.1"

echo ""
echo "========================================="
echo "Lane B1 Debug Session Created!"
echo "========================================="
echo "Session name: $SESSION"
echo ""
echo "Pane layout:"
echo "  0: PX4 + Gazebo"
echo "  1: ROS2 graph (main nodes)"
echo "  2: Follow HUD (/gp2/follow/hud)"
echo "  3: Guard status (/gp2/guard/status)"
echo "  4: Perception Hz (/perception/tracks)"
echo "  5: Seen IDs (/gp2/follow/seen_ids)"
echo ""
echo "Commands:"
echo "  Detach: Ctrl+B then D"
echo "  Reattach: tmux attach-session -t $SESSION"
echo "  Kill session: tmux kill-session -t $SESSION"
echo ""
echo "Attaching to session..."
sleep 2

# Attach to the session
exec tmux attach-session -t "$SESSION"
