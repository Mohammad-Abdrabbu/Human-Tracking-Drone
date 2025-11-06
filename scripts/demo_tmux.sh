#!/usr/bin/env bash
# Demo helper: spawns your known-good panes with labels A, A2, D, E, M, C, T, T2, H

SESSION="gp2_demo"
tmux new-session -d -s $SESSION

# A: PX4 SITL
tmux rename-window -t $SESSION:0 'A'
tmux send-keys -t $SESSION:0 'cd ~/gp2/third_party/PX4-Autopilot && make px4_sitl gz_x500_mono_cam' C-m

# A2: QGroundControl
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0.1 'qgroundcontrol' C-m

# D: bridge
tmux new-window -t $SESSION -n 'D'
tmux send-keys 'export GZ_IP=127.0.0.1; source /opt/ros/humble/setup.bash; ros2 run ros_gz_image image_bridge /world/default/model/x500_mono_cam_0/link/camera_link/sensor/imager/image' C-m

# E: YOLO
tmux new-window -t $SESSION -n 'E'
tmux send-keys 'ros2 run gp2_perception yolo_node --ros-args -p model_path:=/home/ramadan/gp2/models/yolov8n.pt -p conf:=0.25 -p imgsz:=512 -p publish_debug_image:=false -r /camera/image_raw:=/world/default/model/x500_mono_cam_0/link/camera_link/sensor/imager/image' C-m

# M: ByteTrack
tmux new-window -t $SESSION -n 'M'
tmux send-keys 'ros2 run gp2_perception bytetrack_node --ros-args -p detections_topic:=/perception/detections -p tracks_topic:=/perception/tracks -p seen_ids_topic:=/perception/seen_ids -p diagnostics_topic:=/perception/diagnostics -p mot_classes:="[\'person\']" -p conf_thres:=0.35 -p track_thresh:=0.50 -p match_thresh:=0.65 -p track_buffer:=60 -p max_age_without_det:=60 -p min_box_area_px:=400.0 -p fps_min:=2.0 -p debug_image_enable:=false' C-m

# C: Follower
tmux new-window -t $SESSION -n 'C'
tmux send-keys 'ros2 run gp2_perception follow_node --ros-args -p udp_url:=udpin://0.0.0.0:14540 -p det_topic:=/dev/null -p tracks_topic:=/perception/tracks -p tracks_qos:=reliable -p require_target_selection:=true -p img_w:=1280 -p img_h:=960 -p hfov_deg:=100.0 -p invert_ex:=false -p k_yaw:=1.2 -p kd_yaw:=0.0 -p lpf_alpha:=0.20 -p deadzone:=0.08 -p center_hold_deg:=1.5 -p yawrate_max:=0.5 -p rate_limit_yaw:=60.0 -p stand_off_px:=300.0 -p max_close_px:=420.0 -p h_deadband_px:=10.0 -p kx:=0.012 -p vx_max:=0.5 -p rate_limit_vx:=0.10 -p gate_ex:=0.35 -p h_lpf_alpha:=0.20 -p allow_reverse:=false -p stale_s:=0.60 -p lock_k:=3 -p scan_when_no_target:=false -p do_auto_takeoff:=true -p auto_takeoff_alt_m:=2.5 -p takeoff_mode:=action -p alt_guard_enable:=true -p alt_max_m:=2.5 -p alt_deadband_m:=0.05 -p k_z_down:=0.8 -p vz_down_max:=0.7' C-m

# T/T2: IDs + select
tmux new-window -t $SESSION -n 'T'
tmux send-keys 'ros2 topic echo /perception/seen_ids' C-m
tmux split-window -v -t $SESSION:$(tmux list-windows -F "#{window_index}" | tail -n1)
tmux send-keys 'ros2 topic pub -1 /perception/target_select std_msgs/Int32 "{data: 1}"' C-m

# H: spawn human
tmux new-window -t $SESSION -n 'H'
tmux send-keys 'export GZ_SIM_RESOURCE_PATH="$HOME/gp2/assets/models:$GZ_SIM_RESOURCE_PATH"; export WORLD=default; gz service -s /world/$WORLD/create --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean --req "name:\"casual_female_A\",allow_renaming:false,pose:{position:{x:6.0,y:0.0,z:0.0},orientation:{z:0,w:1}},sdf_filename:\"model://Casual female\""' C-m

tmux attach -t $SESSION
