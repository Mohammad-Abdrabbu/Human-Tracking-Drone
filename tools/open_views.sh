#!/usr/bin/env bash
set -euo pipefail

# Start/refresh the tmux session in the background (detached)
WITH_RVIZ="${WITH_RVIZ:-0}"
tmuxp load -d ~/.config/tmuxp/gp2-demo.yaml

# Open separate GNOME Terminal windows attached to specific tmux windows
gnome-terminal --title="A: PX4+GZ" \
  -- bash -lc 'tmux attach -t gp2-demo \; select-window -t A'

gnome-terminal --title="DEMC: Bridge|YOLO|MOT|Follow" \
  -- bash -lc 'tmux attach -t gp2-demo \; select-window -t DEMC'

gnome-terminal --title="T: Target Ops" \
  -- bash -lc 'tmux attach -t gp2-demo \; select-window -t T'

# QGC is a GUI app started inside window A2 already; open a terminal for its logs if you like:
gnome-terminal --title="A2: QGC logs" \
  -- bash -lc 'tmux attach -t gp2-demo \; select-window -t A2'

# If you enable RViz, open a window on A3 as well to see its terminal output
if [ "$WITH_RVIZ" = "1" ]; then
  gnome-terminal --title="A3: RViz2" \
    -- bash -lc 'tmux attach -t gp2-demo \; select-window -t A3'
fi

echo "Attached multiple terminals to tmux session 'gp2-demo'. Arrange them as you like."
