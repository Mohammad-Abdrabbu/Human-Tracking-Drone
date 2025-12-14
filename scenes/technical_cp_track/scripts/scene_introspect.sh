#!/usr/bin/env bash
# scenes/technical_cp_track/scripts/scene_introspect.sh
# Scene 1 Introspect - Debug/monitoring terminal for Track Demo

set -e

SESSION_NAME="scene_track_debug"

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"

# Kill existing session if running
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

echo "Starting Scene 1 (Track) Introspect..."

# Create new session (detached)
tmux new-session -d -s $SESSION_NAME -n "introspect"

# === LAYOUT: 4 panes (2x2 grid) ===
tmux split-window -h -t $SESSION_NAME
tmux split-window -v -t 0
tmux split-window -v -t 2

# Source ROS in all panes
for pane in 0 1 2 3; do
    tmux send-keys -t $SESSION_NAME:0.$pane "source /opt/ros/humble/setup.bash && source $SAHTD_ROOT/install/setup.bash && cd $SAHTD_ROOT" C-m
done

# === Pane 0: Topic list ===
tmux select-pane -t 0
tmux send-keys -t $SESSION_NAME "echo '=== TOPIC LIST ===' && sleep 3 && watch -n 2 'ros2 topic list | egrep \"camera|tracks|follow|perception\"'" C-m

# === Pane 1: Track Hz ===
tmux select-pane -t 1
tmux send-keys -t $SESSION_NAME "echo '=== TRACK FPS ===' && sleep 5 && ros2 topic hz /perception/tracks" C-m

# === Pane 2: Node list ===
tmux select-pane -t 2
tmux send-keys -t $SESSION_NAME "echo '=== NODE LIST ===' && sleep 3 && watch -n 3 'ros2 node list'" C-m

# === Pane 3: Follow HUD ===
tmux select-pane -t 3
tmux send-keys -t $SESSION_NAME "echo '=== FOLLOW HUD ===' && sleep 8 && ros2 topic echo /sahtd/follow/hud" C-m

cat << 'EOF'
===================================================
Scene 1 (Track Demo) Introspect Started!
  - Pane 0: Topic list
  - Pane 1: Track FPS
  - Pane 2: Node list  
  - Pane 3: Follow HUD

To reattach: tmux attach -t scene_track_debug
To kill: tmux kill-session -t scene_track_debug
===================================================
EOF

tmux attach -t $SESSION_NAME
