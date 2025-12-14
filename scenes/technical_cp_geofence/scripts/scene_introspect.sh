#!/usr/bin/env bash
# scenes/technical_cp_geofence/scripts/scene_introspect.sh
# Scene 2 Introspect - Geofence alerts/status monitoring terminal

set -e

SESSION_NAME="scene_geofence_debug"

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"

# Kill existing session if running
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

echo "Starting Scene 2 (Geofence) Introspect..."

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

# === Pane 0: Target Status (MAIN - watch for INSIDE→OUTSIDE) ===
tmux select-pane -t 0
tmux send-keys -t $SESSION_NAME "echo '=== TARGET STATUS ===' && sleep 5 && ros2 topic echo /sahtd/guard/target_status" C-m

# === Pane 1: Alerts (watch for violation) ===
tmux select-pane -t 1
tmux send-keys -t $SESSION_NAME "echo '=== ALERTS ===' && sleep 5 && ros2 topic echo /sahtd/alerts" C-m

# === Pane 2: Target Reason / Position ===
tmux select-pane -t 2
tmux send-keys -t $SESSION_NAME "echo '=== TARGET REASON ===' && sleep 5 && ros2 topic echo /sahtd/guard/target_reason" C-m

# === Pane 3: Violator Pose (ground truth) ===
tmux select-pane -t 3
tmux send-keys -t $SESSION_NAME "echo '=== VIOLATOR POSE ===' && sleep 5 && ros2 topic echo /gp2/target_pose_gt/info" C-m

cat << 'EOF'
===================================================
Scene 2 (Geofence Demo) Introspect Started!
  - Pane 0: Target Status (INSIDE / OUTSIDE)
  - Pane 1: Alerts (violation message)
  - Pane 2: Target Reason (distance to edge)
  - Pane 3: Violator Ground Truth Pose

Expected sequence:
  1. TARGET_INSIDE_FENCE (violator walking)
  2. TARGET_NEAR_EDGE (approaching boundary)
  3. TARGET_OUTSIDE_FENCE (VIOLATION!)
  4. Alert published once

To reattach: tmux attach -t scene_geofence_debug
To kill: tmux kill-session -t scene_geofence_debug
===================================================
EOF

tmux attach -t $SESSION_NAME
