#!/usr/bin/env bash
# demo_committee.sh - Committee Demo Orchestrator
# Single command to bring up, configure, and run the full SAHTD demo
#
# Usage:
#   demo_committee.sh up [--guard on|off] [--spawn] [--autoselect] [--world <name>] [--timeout <sec>]
#   demo_committee.sh spawn [--world <name>] [--actor_sdf <path>]
#   demo_committee.sh select [--policy best|first] [--timeout <sec>]
#   demo_committee.sh status
#   demo_committee.sh reset

set -e

# === Colors ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# === Paths ===
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

SESSION_NAME="sahtd_stack"
DEFAULT_WORLD="default"
DEFAULT_ACTOR_SDF="$SAHTD_ROOT/simulation/models/actor_walk_slow/model.sdf"
DEFAULT_TIMEOUT=30

# === Helper Functions ===

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  SAHTD Committee Demo Orchestrator${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_ready() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                     DEMO READY                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    cat << EOF
Usage:
  demo_committee.sh up [--guard on|off] [--spawn] [--autoselect] [--policy best|first] [--world <name>] [--timeout <sec>]
  demo_committee.sh spawn [--world <name>] [--actor_sdf <path>]
  demo_committee.sh select [--policy best|first] [--timeout <sec>]
  demo_committee.sh status
  demo_committee.sh reset

Subcommands:
  up        Start stack (or attach to existing) and configure demo
  spawn     Spawn the target actor in Gazebo
  select    Auto-select a target from visible tracks
  status    Print current system status
  reset     Stop all services and clean up

Options for 'up':
  --guard on|off       Enable or disable geofence (default: on)
  --markers on|off     Spawn fence markers in Gazebo (default: on)
  --spawn              Spawn actor after stack is ready
  --autoselect         Auto-select target after spawn
  --policy best|first  Selection policy for autoselect (default: best)
  --world <name>       Gazebo world name (default: $DEFAULT_WORLD)
  --timeout <sec>      Timeout for topic checks (default: $DEFAULT_TIMEOUT)

Options for 'spawn':
  --world <name>      Gazebo world name (default: $DEFAULT_WORLD)
  --actor_sdf <path>  Custom actor SDF (default: person_committee.sdf)

Options for 'select':
  --policy best|first  Selection policy (default: best)
  --timeout <sec>      Timeout for track detection (default: 10)

Examples:
  demo_committee.sh up --guard on --spawn --autoselect
  demo_committee.sh up --guard on --markers on --spawn --autoselect --policy best
  demo_committee.sh status
  demo_committee.sh reset
EOF
}

is_stack_running() {
    tmux has-session -t $SESSION_NAME 2>/dev/null
}

wait_for_topic() {
    local topic="$1"
    local timeout="$2"
    local start_time=$(date +%s)
    
    while true; do
        if ros2 topic info "$topic" 2>/dev/null | grep -q "Publisher count: [1-9]"; then
            return 0
        fi
        
        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -ge $timeout ]; then
            return 1
        fi
        sleep 1
    done
}

wait_for_gazebo_ready() {
    local world="$1"
    local timeout="${2:-30}"
    local start_time=$(date +%s)
    
    echo -n "  Waiting for Gazebo world '$world' to be ready... "
    
    while true; do
        # Check if the world's create service exists (means Gazebo is up)
        if gz service -l 2>/dev/null | grep -q "/world/$world/create"; then
            # Additional check: see if drone model exists
            if gz model -m x500_lidar -l 2>/dev/null | grep -q "x500_lidar" || \
               gz service -l 2>/dev/null | grep -q "/world/$world/"; then
                echo -e "${GREEN}✓${NC}"
                # Small extra delay for stability
                sleep 2
                return 0
            fi
        fi
        
        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -ge $timeout ]; then
            echo -e "${YELLOW}timeout (continuing anyway)${NC}"
            return 0  # Don't fail, just continue
        fi
        sleep 1
    done
}

# === Subcommand: up ===

cmd_up() {
    local guard="on"
    local markers="on"
    local spawn=false
    local autoselect=false
    local world="$DEFAULT_WORLD"
    local timeout=$DEFAULT_TIMEOUT
    local policy="best"
    
    # Parse args
    while [[ $# -gt 0 ]]; do
        case $1 in
            --guard) guard="$2"; shift 2 ;;
            --markers) markers="$2"; shift 2 ;;
            --spawn) spawn=true; shift ;;
            --autoselect) autoselect=true; shift ;;
            --world) world="$2"; shift 2 ;;
            --timeout) timeout="$2"; shift 2 ;;
            --policy) policy="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    
    print_header
    
    # Step 1: Start or attach to stack
    if is_stack_running; then
        echo -e "${GREEN}✓ Stack already running${NC}"
    else
        echo -e "${YELLOW}Starting stack...${NC}"
        # Start stack in background (don't attach)
        tmux new-session -d -s $SESSION_NAME -n "stack"
        tmux split-window -v -t $SESSION_NAME
        tmux select-pane -t 0
        tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT && $SAHTD_ROOT/scripts/core/start_px4.sh" C-m
        tmux select-pane -t 1
        tmux send-keys -t $SESSION_NAME "cd $SAHTD_ROOT && sleep 15 && $SAHTD_ROOT/scripts/core/start_ros.sh" C-m
        echo -e "${YELLOW}  Stack starting in background (tmux: $SESSION_NAME)${NC}"
    fi
    
    # Step 2: Wait for critical topics
    echo ""
    echo -e "${YELLOW}Waiting for critical topics (timeout: ${timeout}s)...${NC}"
    
    local topics=("/gp2/vehicle/pose_local" "/gp2/guard/status" "/perception/tracks")
    local all_ok=true
    
    for topic in "${topics[@]}"; do
        echo -n "  Checking $topic... "
        if wait_for_topic "$topic" "$timeout"; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ (timeout)${NC}"
            all_ok=false
        fi
    done
    
    if [ "$all_ok" = false ]; then
        echo ""
        echo -e "${RED}Some topics not ready. Check stack health.${NC}"
        echo "  Run: tmux attach -t $SESSION_NAME"
        exit 1
    fi
    
    # Step 3: Configure guard
    echo ""
    if [ "$guard" = "off" ]; then
        echo -e "${YELLOW}Disabling geofence...${NC}"
        ros2 param set /geo_guard_node guard_enabled false 2>/dev/null && \
            echo -e "${GREEN}  ✓ Guard disabled${NC}" || \
            echo -e "${YELLOW}  ⚠ Could not set param (node may need restart)${NC}"
    else
        echo -e "${GREEN}✓ Geofence enabled (default)${NC}"
        ros2 param set /geo_guard_node guard_enabled true 2>/dev/null || true
    fi
    
    # Step 4: Spawn fence markers
    if [ "$markers" = "on" ]; then
        echo ""
        echo -e "${YELLOW}Spawning fence markers...${NC}"
        python3 "$SCRIPT_DIR/spawn_fence_markers.py" --world "$world" && \
            echo -e "${GREEN}  ✓ Fence markers visible${NC}" || \
            echo -e "${YELLOW}  ⚠ Could not spawn markers (continuing anyway)${NC}"
    fi
    
    # Step 5: Spawn actor
    if [ "$spawn" = true ]; then
        echo ""
        cmd_spawn --world "$world"
        # Give actor a moment to appear in perception
        echo "  Waiting for actor to be detected..."
        sleep 3
    fi
    
    # Step 5: Auto-select
    if [ "$autoselect" = true ]; then
        echo ""
        cmd_select --policy "$policy" --timeout 10
    fi
    
    # Final status
    print_ready
    
    echo -e "${CYAN}Current Status:${NC}"
    
    # Get latest debug
    local debug_line=$(timeout 2 ros2 topic echo /gp2/guard/debug --once 2>/dev/null | grep "data:" | head -1 | sed 's/data: //' || echo "N/A")
    echo "  Guard: $debug_line"
    
    echo ""
    echo -e "${CYAN}Hints:${NC}"
    echo "  To change target: ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: <ID>}' --once"
    echo "  To view guard:    ros2 topic echo /gp2/guard/debug"
    echo "  To attach stack:  tmux attach -t $SESSION_NAME"
    echo ""
}

# === Subcommand: spawn ===

cmd_spawn() {
    local world="$DEFAULT_WORLD"
    local actor_sdf="$DEFAULT_ACTOR_SDF"
    local timeout=30
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --world) world="$2"; shift 2 ;;
            --actor_sdf) actor_sdf="$2"; shift 2 ;;
            --timeout) timeout="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    
    echo -e "${YELLOW}Spawning actor...${NC}"
    echo "  World: $world"
    echo "  SDF: $(basename $actor_sdf)"
    
    if [ ! -f "$actor_sdf" ]; then
        echo -e "${RED}Error: SDF file not found: $actor_sdf${NC}"
        exit 1
    fi
    
    # Wait for Gazebo world to be ready (drone spawned)
    wait_for_gazebo_ready "$world" "$timeout"
    
    # Spawn via Gazebo service using sdf_filename (path) - matches spawn_actor.sh
    # Position: 3m in front of drone, slightly above ground
    gz service -s /world/$world/create \
        --reqtype gz.msgs.EntityFactory \
        --reptype gz.msgs.Boolean \
        --timeout 5000 \
        --req "sdf_filename: \"$actor_sdf\", name: \"human_target\", allow_renaming: true, pose: {position: {x: 3.0, y: 0.0, z: 1.0}}" && \
        echo -e "${GREEN}  ✓ Actor spawned${NC}" || \
        echo -e "${RED}  ✗ Failed to spawn (is Gazebo running?)${NC}"
}

# === Subcommand: select ===

cmd_select() {
    local policy="best"
    local timeout=10
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --policy) policy="$2"; shift 2 ;;
            --timeout) timeout="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    
    echo -e "${YELLOW}Auto-selecting target (policy: $policy, timeout: ${timeout}s)...${NC}"
    
    # Run Python helper
    python3 "$SCRIPT_DIR/auto_select_target.py" --policy "$policy" --timeout "$timeout"
}

# === Subcommand: status ===

cmd_status() {
    print_header
    
    echo -e "${CYAN}System Status:${NC}"
    echo ""
    
    # Stack
    if is_stack_running; then
        echo -e "  Stack: ${GREEN}RUNNING${NC} (tmux: $SESSION_NAME)"
    else
        echo -e "  Stack: ${RED}NOT RUNNING${NC}"
    fi
    
    # Pose local
    echo -n "  Pose Local: "
    local pose_hz=$(timeout 2 ros2 topic hz /gp2/vehicle/pose_local 2>&1 | grep "average rate" | tail -1 | awk '{print $3}' || echo "0")
    if [ -n "$pose_hz" ] && [ "$pose_hz" != "0" ]; then
        echo -e "${GREEN}${pose_hz} Hz${NC}"
    else
        echo -e "${RED}Not publishing${NC}"
    fi
    
    # Guard debug
    echo -n "  Guard Debug: "
    local debug=$(timeout 2 ros2 topic echo /gp2/guard/debug --once 2>/dev/null | grep "data:" | sed 's/data: //' || echo "N/A")
    echo "$debug"
    
    # Guard status
    echo -n "  Guard Status: "
    local status=$(timeout 2 ros2 topic echo /gp2/guard/status --once 2>/dev/null | grep "data:" | sed 's/data: //' || echo "N/A")
    echo "$status"
    
    # Visible IDs
    echo -n "  Visible IDs: "
    local ids=$(timeout 2 ros2 topic echo /sahtd/follow/seen_ids --once 2>/dev/null | grep "data:" | sed 's/data: //' || echo "N/A")
    echo "$ids"
    
    echo ""
}

# === Subcommand: reset ===

cmd_reset() {
    echo -e "${YELLOW}Resetting demo...${NC}"
    
    # Remove fence markers (best-effort)
    if [ -f "$SCRIPT_DIR/remove_fence_markers.sh" ]; then
        echo -e "${YELLOW}Removing fence markers...${NC}"
        bash "$SCRIPT_DIR/remove_fence_markers.sh" 2>/dev/null || true
    fi
    
    # Use existing reset script if available
    if [ -f "$SAHTD_ROOT/scripts/debug/reset_demo.sh" ]; then
        bash "$SAHTD_ROOT/scripts/debug/reset_demo.sh"
    else
        # Fallback inline reset
        tmux kill-session -t $SESSION_NAME 2>/dev/null || true
        killall -9 gz px4 ruby gzserver gzclient 2>/dev/null || true
        ros2 daemon stop 2>/dev/null; sleep 1; ros2 daemon start 2>/dev/null || true
    fi
    
    echo ""
    echo -e "${GREEN}RESET DONE${NC}"
}

# === Main ===

if [[ $# -eq 0 ]]; then
    print_usage
    exit 0
fi

# Source ROS
source /opt/ros/humble/setup.bash 2>/dev/null || true
source "$SAHTD_ROOT/install/setup.bash" 2>/dev/null || true
source "$SAHTD_ROOT/ros2/install/setup.bash" 2>/dev/null || true

case $1 in
    up) shift; cmd_up "$@" ;;
    spawn) shift; cmd_spawn "$@" ;;
    select) shift; cmd_select "$@" ;;
    status) cmd_status ;;
    reset) cmd_reset ;;
    -h|--help) print_usage ;;
    *) echo -e "${RED}Unknown command: $1${NC}"; print_usage; exit 1 ;;
esac
