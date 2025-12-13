#!/usr/bin/env bash
# scripts/debug/sahtd_introspect.sh
# SAHTD Introspection Dashboard - Monitor all critical topics and state

set -e

SESSION_NAME="sahtd_introspect"

# Resolve SAHTD_ROOT
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

# Kill existing session if running
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

echo "Starting SAHTD Introspection session..."

# Create new session (detached)
tmux new-session -d -s $SESSION_NAME -n "introspect"

# === LAYOUT: 5 panes ===
# +-------------------------------------------+
# |          FOLLOWER HUD (Wide)              |
# +-------------------+-----------------------+
# |   Tracks Hz       |   Camera Hz           |
# +-------------------+-----------------------+
# |   Geo-Guard       |   Command Prompt      |
# +-------------------+-----------------------+

# Split into 3 rows (horizontal splits)
tmux split-window -v -t $SESSION_NAME
tmux split-window -v -t $SESSION_NAME

# Split middle row (pane 1) into 2 columns
tmux select-pane -t 1
tmux split-window -h -t $SESSION_NAME

# Split bottom row (pane 3) into 2 columns
tmux select-pane -t 3
tmux split-window -h -t $SESSION_NAME

# Now we have 5 panes:
# 0: Top (full width) - HUD
# 1: Mid-Left - Tracks Hz
# 2: Mid-Right - Camera Hz
# 3: Bottom-Left - Geo-Guard
# 4: Bottom-Right - Command Prompt

# === Pane 0 (Top Full-Width): Follower HUD ===
tmux select-pane -t 0
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source ros2/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME "clear && echo '=== FOLLOWER HUD (WIDE) ===' && echo 'Waiting for /sahtd/follow/hud...' && sleep 2" C-m
tmux send-keys -t $SESSION_NAME "ros2 topic echo /sahtd/follow/hud" C-m

# === Pane 1 (Mid-Left): Tracks Publishing Rate ===
tmux select-pane -t 1
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source ros2/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME "clear && echo '=== TRACKS RATE ===' && echo 'Waiting for /perception/tracks...' && sleep 2" C-m
tmux send-keys -t $SESSION_NAME "ros2 topic hz /perception/tracks" C-m

# === Pane 2 (Mid-Right): Camera Publishing Rate ===
tmux select-pane -t 2
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source ros2/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME "clear && echo '=== CAMERA RATE ===' && echo 'Waiting for /camera/image_raw...' && sleep 2" C-m
tmux send-keys -t $SESSION_NAME "ros2 topic hz /camera/image_raw" C-m

# === Pane 3 (Bottom-Left): Geo-Guard Status ===
tmux select-pane -t 3
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source ros2/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME "clear && echo '=== GEO-GUARD STATUS ===' && echo 'Waiting for /gp2/guard/status...' && sleep 2" C-m
tmux send-keys -t $SESSION_NAME "ros2 topic echo /gp2/guard/status" C-m

# === Pane 4 (Bottom-Right): Command Prompt ===
tmux select-pane -t 4
tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT" C-m
tmux send-keys -t $SESSION_NAME "source /opt/ros/humble/setup.bash && source ros2/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME "clear" C-m
tmux send-keys -t $SESSION_NAME "echo '=== COMMAND PROMPT ==='" C-m
tmux send-keys -t $SESSION_NAME "echo 'Quick commands:'" C-m
tmux send-keys -t $SESSION_NAME "echo '  doctor.sh - health check'" C-m
tmux send-keys -t $SESSION_NAME "echo '  spawn_actor.sh slow - spawn human'" C-m
tmux send-keys -t $SESSION_NAME "echo '  ros2 topic pub --once /perception/target_select std_msgs/msg/Int32 \"{data: 1}\" - select'" C-m
tmux send-keys -t $SESSION_NAME "echo ''" C-m

# Adjust pane sizes (larger HUD at top)
tmux select-pane -t 0
tmux resize-pane -y 10

# Start in command prompt pane
tmux select-pane -t 4

# Attach to session
echo ""
echo "==================================================="
echo "SAHTD Introspection Dashboard started!"
echo ""
echo "Layout:"
echo "  Top (Wide): Follower HUD (/sahtd/follow/hud)"
echo "  Mid-Left: Tracks rate (20 Hz expected)"
echo "  Mid-Right: Camera rate (30 Hz expected)"
echo "  Bottom-Left: Geo-guard status"
echo "  Bottom-Right: Command prompt (active)"
echo ""
echo "Controls:"
echo "  Ctrl+b, arrow keys - switch panes"
echo "  Ctrl+b, [ - scroll mode (q to exit)"
echo "  Ctrl+b, d - detach (keeps running)"
echo ""
echo "To reattach: tmux attach -t $SESSION_NAME"
echo "To kill: tmux kill-session -t $SESSION_NAME"
echo "==================================================="
echo ""

tmux attach -t $SESSION_NAME
