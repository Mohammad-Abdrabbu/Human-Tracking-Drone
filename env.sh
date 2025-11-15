# ===== GP2 global environment =====
# ROS 2
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash

# GP2 workspace overlay ONLY
[ -f "$HOME/gp2/ws/gp2_ws/install/setup.bash" ] && \
  source "$HOME/gp2/ws/gp2_ws/install/setup.bash"

# Common vars
export ROS_DOMAIN_ID=0
export GZ_VERSION=harmonic
export GZ_IP=127.0.0.1

# Models path (prepend your assets)
if [ -d "$HOME/gp2/assets/models" ]; then
  case ":$GZ_SIM_RESOURCE_PATH:" in
    *":$HOME/gp2/assets/models:"*) ;; # already present
    *) export GZ_SIM_RESOURCE_PATH="$HOME/gp2/assets/models:${GZ_SIM_RESOURCE_PATH:-}";;
  esac
fi
