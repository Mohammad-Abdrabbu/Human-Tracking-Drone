#!/bin/bash
# demo_fitexpo.sh
# Connects CLI commands to systemd services
# Updates: Accepts all committee demo flags and writes detailed config

set -e

SERVICE_Target="fitexpo.target"

print_usage() {
    echo "Usage: demo_fitexpo.sh [command] [options]"
    echo "Commands:"
    echo "  start      Start fitexpo demo services"
    echo "  stop       Stop fitexpo demo services"
    echo "  reset      Stop and deep clean all processes"
    echo "  status     Check status"
    echo "  install    Install systemd services (requires sudo)"
    echo "Options for start:"
    echo "  --headless         Run without GUI"
    echo "  --spawn            Spawn walking actor"
    echo "  --extras <N>       Spawn N extra humans"
    echo "  --guard on|off     Enable/disable geofence"
    echo "  --markers on|off   Enable/disable markers"
    echo "  --events on|off    Enable/disable event log"
    echo "  --video on|off     Enable/disable video bridge"
}

cmd_install() {
    echo "Installing services..."
    sudo bash $(dirname $0)/install_services.sh
}

cmd_start() {
    echo "Starting FitExpo Demo..."
    
    # Defaults matching committee demo
    HEADLESS=0
    SPAWN_WALKER=0
    EXTRAS=0
    GUARD_ENABLED=1
    MARKERS_ENABLED=1
    EVENTS_ENABLED=1
    VIDEO_ENABLED=0
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --extras) EXTRAS="$2"; shift 2 ;;
            --headless) HEADLESS=1; shift ;;
            --spawn) SPAWN_WALKER=1; shift ;;
            --guard) [ "$2" = "off" ] && GUARD_ENABLED=0; shift 2 ;;
            --markers) [ "$2" = "off" ] && MARKERS_ENABLED=0; shift 2 ;;
            --events) [ "$2" = "off" ] && EVENTS_ENABLED=0; shift 2 ;;
            --video) [ "$2" = "on" ] && VIDEO_ENABLED=1; shift 2 ;;
            *) shift ;;
        esac
    done
    
    # Write full config for orchestrator
    CONFIG="/tmp/sahtd_fitexpo_config"
    cat << EOF > "$CONFIG"
HEADLESS=$HEADLESS
EXTRAS=$EXTRAS
SPAWN_WALKER=$SPAWN_WALKER
GUARD_ENABLED=$GUARD_ENABLED
MARKERS_ENABLED=$MARKERS_ENABLED
EVENTS_ENABLED=$EVENTS_ENABLED
VIDEO_ENABLED=$VIDEO_ENABLED
EOF
    
    # Stop first
    sudo systemctl stop $SERVICE_Target
    
    # Start
    sudo systemctl start $SERVICE_Target
    
    echo "Services started. Check status with: $0 status"
    echo "Follow logs: sudo journalctl -u fitexpo-orchestrator.service -f"
}

cmd_stop() {
    echo "Stopping FitExpo Demo..."
    sudo systemctl stop $SERVICE_Target
}

cmd_reset() {
    echo "Resetting FitExpo Demo (Deep Clean)..."
    sudo systemctl stop $SERVICE_Target
    
    echo "Killing lingering processes..."
    pkill -f "px4" || true
    pkill -f "gz server" || true
    pkill -f "gz client" || true
    pkill -f "ruby" || true
    pkill -f "component_container" || true
    pkill -f "event_logger_node" || true
    pkill -f "telemetry_bridge_node" || true
    pkill -f "video_bridge_node" || true
    
    echo "Restarting ROS2 daemon..."
    ros2 daemon stop >/dev/null 2>&1 || true
    ros2 daemon start >/dev/null 2>&1 || true
    
    rm -f /tmp/sahtd_fitexpo_config
    echo "Reset complete."
}

cmd_status() {
    sudo systemctl status $SERVICE_Target fitexpo-px4.service fitexpo-ros.service fitexpo-orchestrator.service
}

if [[ $# -eq 0 ]]; then
    print_usage
    exit 0
fi

CMD=$1
shift

case $CMD in
    start) cmd_start "$@" ;;
    stop) cmd_stop "$@" ;;
    reset) cmd_reset "$@" ;;
    status) cmd_status "$@" ;;
    install) cmd_install "$@" ;;
    *) print_usage ;;
esac
