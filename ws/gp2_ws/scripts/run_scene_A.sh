#!/usr/bin/env bash
set -euo pipefail

# ---- Paths ----
GP2_WS="$HOME/gp2/ws/gp2_ws"
ROS_GZ_WS="$HOME/gp2/ws/ros_gz_harm_ws"
PX4_DIR="$HOME/gp2/third_party/PX4-Autopilot"
PARAMS="$GP2_WS/params/scenes/scene_A.yaml"

SESSION="gp2_sceneA"

# ---- Clean + start session ----
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -n "A (PX4)"

# A: PX4 SITL (spawns Gazebo Harmonic with gz_x500_mono_cam)
tmux send-keys -t "$SESSION:0" "cd '$PX4_DIR'" C-m
tmux send-keys -t "$SESSION:0" "make px4_sitl gz_x500_mono_cam" C-m

# D: ros_gz_image bridge (Harmonic → ROS)
tmux new-window -t "$SESSION:1" -n "D (Bridge)"
tmux send-keys -t "$SESSION:1" \
  "source '/opt/ros/humble/setup.bash'; \
   source '$ROS_GZ_WS/install/setup.bash' 2>/dev/null || true; \
   source '$GP2_WS/install/setup.bash' 2>/dev/null || true; \
   export GZ_IP=127.0.0.1; \
   ros2 run ros_gz_image image_bridge --ros-args \
     -r /camera/image_raw:=/world/default/model/x500_mono_cam_0/link/camera_link/sensor/imager/image" C-m

# M: ByteTrack (detector + MOT)
tmux new-window -t "$SESSION:2" -n "M (MOT)"
tmux send-keys -t "$SESSION:2" \
  "source '/opt/ros/humble/setup.bash'; \
   source '$GP2_WS/install/setup.bash' 2>/dev/null || true; \
   ros2 run gp2_perception bytetrack_node --ros-args --params-file '$PARAMS'" C-m

# C: Follow node (MAVSDK Offboard)
tmux new-window -t "$SESSION:3" -n "C (Follow)"
tmux send-keys -t "$SESSION:3" \
  "source '/opt/ros/humble/setup.bash'; \
   source '$GP2_WS/install/setup.bash' 2>/dev/null || true; \
   ros2 run gp2_perception follow_node --ros-args --params-file '$PARAMS'" C-m

tmux setw -t "$SESSION" remain-on-exit on
tmux select-window -t "$SESSION:0"
tmux attach -t "$SESSION"
