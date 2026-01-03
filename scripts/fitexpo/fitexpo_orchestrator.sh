#!/bin/bash
# fitexpo_orchestrator.sh
# Faithfully duplicates logic from demo_committee.sh for proper pacing and sequence
# Runs as part of fitexpo-orchestrator.service (Type=simple, long-running)

set -e

# === Configuration ===
CONFIG_FILE="/tmp/sahtd_fitexpo_config"
WORLD="default"
TIMEOUT=60
SAHTD_ROOT=${SAHTD_ROOT:-$HOME/sahtd}

# Source ROS and Workspace
source /opt/ros/humble/setup.bash
source $SAHTD_ROOT/install/setup.bash
source $SAHTD_ROOT/ros2/install/setup.bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "$1"
}

# Values from config
HEADLESS=0
EXTRAS=0
SPAWN_WALKER=0
GUARD_ENABLED=1
MARKERS_ENABLED=1
EVENTS_ENABLED=1
VIDEO_ENABLED=1

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Track background PIDs
PIDS=""

cleanup() {
    log "${YELLOW}Orchestrator stopping - cleaning up background processes...${NC}"
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null || true
    fi
}
trap cleanup EXIT

# === Helpers ===

wait_for_topic() {
    local topic="$1"
    local timeout="$2"
    local start_time=$(date +%s)
    
    echo -n "  Checking $topic... "
    
    while true; do
        if ros2 topic info "$topic" 2>/dev/null | grep -q "Publisher count: [1-9]"; then
            log "${GREEN}✓${NC}"
            return 0
        fi
        
        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -ge $timeout ]; then
            log "${RED}timeout${NC}"
            return 1
        fi
        sleep 1
    done
}

wait_for_gazebo_ready() {
    local world="$1"
    local timeout="$2"
    local start_time=$(date +%s)
    
    [ "$HEADLESS" -eq 1 ] && return 0
    
    log "  Waiting for Gazebo world '$world'..."
    while true; do
        if gz service -l 2>/dev/null | grep -q "/world/$world/create"; then
            if gz model -m x500_lidar -l 2>/dev/null | grep -q "x500_lidar" || \
               gz service -l 2>/dev/null | grep -q "/world/$world/"; then
                log "${GREEN}  ✓ Gazebo ready${NC}"
                sleep 2
                return 0
            fi
        fi
        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -ge $timeout ]; then
            log "${YELLOW}  timeout (continuing)${NC}"
            return 0
        fi
        sleep 1
    done
}

# === Sequence (Matching demo_committee.sh) ===

log "${GREEN}SAHTD Fit Expo Orchestrator${NC}"
log "Waiting for critical topics (timeout: ${TIMEOUT}s)..."

wait_for_topic "/gp2/vehicle/pose_local" $TIMEOUT
wait_for_topic "/gp2/guard/status" $TIMEOUT
wait_for_topic "/perception/tracks" $TIMEOUT

# Step 3: Configure Guard
if [ "$GUARD_ENABLED" -eq 1 ]; then
    log "${GREEN}✓ Geofence enabled (default)${NC}"
    ros2 param set /geo_guard_node guard_enabled true 2>/dev/null || true
else
    log "${YELLOW}Disabling geofence...${NC}"
    ros2 param set /geo_guard_node guard_enabled false 2>/dev/null
fi

# Step 4: Spawn Markers
if [ "$MARKERS_ENABLED" -eq 1 ]; then
    log "Spawning fence markers..."
    # Wait for Gazebo mainly for visual things
    wait_for_gazebo_ready "$WORLD" $TIMEOUT
    python3 "$SAHTD_ROOT/scripts/fitexpo/spawn_markers.py" --world "$WORLD"
    log "${GREEN}  ✓ Fence markers visible${NC}"
fi

# Step 4b: Start Event Logger
if [ "$EVENTS_ENABLED" -eq 1 ]; then
    log "Starting event logger..."
    if ros2 node list 2>/dev/null | grep -q "event_logger_node"; then
        log "${GREEN}  ✓ Event logger already running${NC}"
    else
        ros2 run sahtd_autonomy event_logger_node &
        PID=$!
        PIDS="$PIDS $PID"
        sleep 1
        log "${GREEN}  ✓ Event logger started (PID $PID)${NC}"
    fi
fi

# Step 4c: Start Telemetry Bridge
log "Starting telemetry bridge..."
if ros2 node list 2>/dev/null | grep -q "telemetry_bridge_node"; then
    log "${GREEN}  ✓ Telemetry bridge already running${NC}"
else
    ros2 run sahtd_web_bridge telemetry_bridge_node &
    PID=$!
    PIDS="$PIDS $PID"
    sleep 1
    log "${GREEN}  ✓ Telemetry bridge started (PID $PID)${NC}"
fi

# Step 4d: Start Video Bridge
if [ "$VIDEO_ENABLED" -eq 1 ]; then
    log "Starting video bridge..."
    if ros2 node list 2>/dev/null | grep -q "video_bridge_node"; then
        log "${GREEN}  ✓ Video bridge already running${NC}"
    else
        ros2 run sahtd_web_bridge video_bridge_node &
        PID=$!
        PIDS="$PIDS $PID"
        sleep 1
        log "${GREEN}  ✓ Video bridge started (PID $PID)${NC}"
    fi
fi

# Step 5: Spawn Walking Actor
if [ "$SPAWN_WALKER" -eq 1 ]; then
    log "Spawning walking actor..."
    python3 "$SAHTD_ROOT/scripts/fitexpo/spawn_actors.py" --world "$WORLD" --spawn_walker
    log "${GREEN}  ✓ Actor spawned${NC}"
fi

# Step 5b: Spawn Extras
if [ "$EXTRAS" -gt 0 ]; then
    log "Spawning $EXTRAS extra standing humans..."
    python3 "$SAHTD_ROOT/scripts/fitexpo/spawn_actors.py" --world "$WORLD" --extras "$EXTRAS"
    log "${GREEN}  ✓ Extras spawned${NC}"
fi

log "${GREEN}Orchestration startup complete. Running bridges in background...${NC}"

# Loop forever to keep bridges alive (systemd handles lifecycle)
while true; do
    sleep 5
done
