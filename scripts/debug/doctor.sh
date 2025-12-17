#!/usr/bin/env bash
# scripts/debug/doctor.sh
# System health check for SAHTD demo
# Returns: 0=healthy, 1=critical failure, 2=warnings

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Symbols
PASS="${GREEN}✓${NC}"
FAIL="${RED}✗${NC}"
WARN="${YELLOW}⚠${NC}"
INFO="${BLUE}ℹ${NC}"

# Track overall health
CRITICAL_FAIL=0
WARNINGS=0

echo -e "\n========================================"
echo "SAHTD System Health Check"
echo -e "========================================\n"

# ============================================
# PROCESS CHECKS
# ============================================
echo -e "${BLUE}[PROCESSES]${NC}"

# Check PX4
if pgrep -f "px4.*sitl" > /dev/null; then
    PX4_PID=$(pgrep -f "px4.*sitl" | head -1)
    echo -e "${PASS} PX4 SITL running (PID: $PX4_PID)"
else
    echo -e "${FAIL} PX4 SITL NOT running"
    CRITICAL_FAIL=1
fi

# Check Gazebo
if pgrep -f "gz sim" > /dev/null; then
    GZ_PID=$(pgrep -f "gz sim" | head -1)
    echo -e "${PASS} Gazebo Sim running (PID: $GZ_PID)"
    
    # Check if correct model spawned
    if command -v gz &> /dev/null; then
        if timeout 2 gz topic -l 2>/dev/null | grep -q "x500_mono_cam_0.*image"; then
            echo -e "${PASS} Drone model: x500_mono_cam (with camera)"
        else
            echo -e "${WARN} Drone model: might not have camera (check manually)"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
else
    echo -e "${FAIL} Gazebo Sim NOT running"
    CRITICAL_FAIL=1
fi

# Check ROS environment
if ! command -v ros2 &> /dev/null; then
    echo -e "${FAIL} ROS 2 environment NOT sourced"
    # Compute repo root from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SAHTD_ROOT="${SAHTD_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
    echo -e "${INFO} Run: source /opt/ros/humble/setup.bash && source ${SAHTD_ROOT}/ros2/install/setup.bash"
    exit 1
fi

# Check ROS nodes
NODE_COUNT=$(timeout 3 ros2 node list 2>/dev/null | wc -l || echo "0")
if [ "$NODE_COUNT" -ge 8 ]; then
    echo -e "${PASS} ROS 2 graph active ($NODE_COUNT nodes)"
elif [ "$NODE_COUNT" -gt 0 ]; then
    echo -e "${WARN} ROS 2 graph partial ($NODE_COUNT nodes, expected ~9)"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${FAIL} ROS 2 graph NOT active"
    CRITICAL_FAIL=1
fi

# ============================================
# TOPIC HEALTH CHECKS
# ============================================
echo -e "\n${BLUE}[TOPICS - Publishing Rate]${NC}"

# Helper function to check topic hz
check_topic_hz() {
    local topic=$1
    local min_hz=$2
    local timeout_sec=${3:-3}
    
    # Check if topic exists
    if ! timeout 2 ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        echo -e "${FAIL} ${topic}: NOT FOUND"
        CRITICAL_FAIL=1
        return
    fi
    
    # Check publishing rate
    local hz_output=$(timeout $timeout_sec ros2 topic hz "$topic" 2>&1 || echo "")
    
    if echo "$hz_output" | grep -q "average rate:"; then
        local hz=$(echo "$hz_output" | grep "average rate:" | awk '{print $3}')
        if (( $(echo "$hz >= $min_hz" | bc -l) )); then
            echo -e "${PASS} ${topic}: ${hz} Hz"
        else
            echo -e "${WARN} ${topic}: ${hz} Hz (low, expected >$min_hz)"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "${FAIL} ${topic}: NOT PUBLISHING"
        CRITICAL_FAIL=1
    fi
}

# Check camera
check_topic_hz "/camera/image_raw" 20 3

# Check tracks
check_topic_hz "/perception/tracks" 10 3

# Check follower commands
check_topic_hz "/sahtd/follow/cmd_body" 15 3

# ============================================
# SYSTEM STATE CHECKS
# ============================================
echo -e "\n${BLUE}[SYSTEM STATE]${NC}"

# Check target selection
if timeout 2 ros2 topic echo /sahtd/follow/seen_ids --once 2>/dev/null > /tmp/sahtd_seen_ids.txt; then
    SEEN_IDS=$(cat /tmp/sahtd_seen_ids.txt | grep "data:" | cut -d'"' -f2)
    if [ -z "$SEEN_IDS" ] || [ "$SEEN_IDS" = "ids=" ]; then
        echo -e "${WARN} Visible targets: NONE"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${INFO} Visible targets: ${SEEN_IDS}"
    fi
    rm -f /tmp/sahtd_seen_ids.txt
else
    echo -e "${WARN} Target visibility: UNKNOWN"
    WARNINGS=$((WARNINGS + 1))
fi

# Check drone altitude (from HUD)
if timeout 2 ros2 topic echo /sahtd/follow/hud --once 2>/dev/null > /tmp/sahtd_hud.txt; then
    ALT=$(cat /tmp/sahtd_hud.txt | grep "data:" | grep -oP "alt=\K[0-9.]+")
    if [ ! -z "$ALT" ]; then
        echo -e "${INFO} Drone altitude: ${ALT} m"
    fi
    rm -f /tmp/sahtd_hud.txt
fi

# Check geo-guard status
if timeout 2 ros2 topic echo /gp2/guard/status --once 2>/dev/null > /tmp/sahtd_guard.txt; then
    GUARD_STATUS=$(cat /tmp/sahtd_guard.txt | grep "data:" | cut -d'"' -f2)
    if [ "$GUARD_STATUS" = "CLEAR" ] || [ "$GUARD_STATUS" = "NORMAL" ]; then
        echo -e "${PASS} Geo-guard: ${GUARD_STATUS}"
    else
        echo -e "${WARN} Geo-guard: ${GUARD_STATUS}"
        WARNINGS=$((WARNINGS + 1))
    fi
    rm -f /tmp/sahtd_guard.txt
else
    echo -e "${INFO} Geo-guard: status unknown"
fi

# ============================================
# SUMMARY
# ============================================
echo -e "\n========================================"
if [ $CRITICAL_FAIL -eq 1 ]; then
    echo -e "${FAIL} STATUS: ${RED}CRITICAL FAILURE${NC}"
    echo "Cannot run demo - fix critical issues above"
    echo -e "========================================\n"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${WARN} STATUS: ${YELLOW}READY (${WARNINGS} warning(s))${NC}"
    echo "Demo can run but watch for issues"
    echo -e "========================================\n"
    exit 2
else
    echo -e "${PASS} STATUS: ${GREEN}ALL SYSTEMS GO${NC}"
    echo "Demo ready to run!"
    echo -e "========================================\n"
    exit 0
fi
