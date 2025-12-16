#!/bin/bash
# check_pose_local.sh - Verify /gp2/vehicle/pose_local is publishing correctly
# Usage: ./check_pose_local.sh
# For SAHTD technical checkpoint demonstration

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  SAHTD Pose Local Verification Script"
echo "=============================================="
echo ""

# Check 1: Publisher exists
echo -e "${YELLOW}[1/4] Checking if publisher exists...${NC}"
TOPIC_INFO=$(ros2 topic info -v /gp2/vehicle/pose_local 2>&1 || true)

if echo "$TOPIC_INFO" | grep -q "Publisher count: 0"; then
    echo -e "${RED}✗ FAIL: No publisher found for /gp2/vehicle/pose_local${NC}"
    echo "$TOPIC_INFO"
    exit 1
elif echo "$TOPIC_INFO" | grep -q "Publisher count:"; then
    echo -e "${GREEN}✓ PASS: Publisher exists${NC}"
    echo "$TOPIC_INFO" | grep -E "(Publisher count|Node name)"
else
    echo -e "${RED}✗ FAIL: Topic does not exist${NC}"
    echo "$TOPIC_INFO"
    exit 1
fi
echo ""

# Check 2: Verify QoS
echo -e "${YELLOW}[2/4] Checking QoS settings...${NC}"
if echo "$TOPIC_INFO" | grep -q "Reliability: Reliable"; then
    echo -e "${GREEN}✓ PASS: QoS is RELIABLE${NC}"
else
    echo -e "${YELLOW}⚠ WARNING: QoS may not be RELIABLE${NC}"
fi
echo ""

# Check 3: Check publishing rate
echo -e "${YELLOW}[3/4] Measuring publishing rate (5 seconds)...${NC}"
HZ_OUTPUT=$(timeout 5 ros2 topic hz /gp2/vehicle/pose_local 2>&1 || true)

if echo "$HZ_OUTPUT" | grep -q "average rate:"; then
    RATE=$(echo "$HZ_OUTPUT" | grep "average rate:" | tail -1 | awk '{print $3}')
    echo "Measured rate: $RATE Hz"
    
    # Check if rate is >= 10 Hz (using bc for float comparison)
    if (( $(echo "$RATE >= 10" | bc -l) )); then
        echo -e "${GREEN}✓ PASS: Rate >= 10 Hz${NC}"
    else
        echo -e "${RED}✗ FAIL: Rate < 10 Hz (got $RATE Hz)${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ FAIL: No messages received in 5 seconds${NC}"
    echo "$HZ_OUTPUT"
    exit 1
fi
echo ""

# Check 4: Sample message
echo -e "${YELLOW}[4/4] Sampling one pose message...${NC}"
ECHO_OUTPUT=$(timeout 3 ros2 topic echo -n 1 /gp2/vehicle/pose_local 2>&1 || true)

if echo "$ECHO_OUTPUT" | grep -q "position:"; then
    echo -e "${GREEN}✓ PASS: Message received${NC}"
    echo "$ECHO_OUTPUT"
else
    echo -e "${RED}✗ FAIL: Could not receive message${NC}"
    echo "$ECHO_OUTPUT"
    exit 1
fi
echo ""

# Bonus: Check diagnostic topic
echo -e "${YELLOW}[BONUS] Checking diagnostic topic...${NC}"
DIAG_OUTPUT=$(timeout 3 ros2 topic echo -n 1 /gp2/vehicle/pose_debug 2>&1 || true)

if echo "$DIAG_OUTPUT" | grep -q "enu="; then
    echo -e "${GREEN}✓ PASS: Diagnostic topic working${NC}"
    echo "$DIAG_OUTPUT"
else
    echo -e "${YELLOW}⚠ INFO: Diagnostic topic not publishing yet (may need MAVSDK)${NC}"
fi
echo ""

echo "=============================================="
echo -e "${GREEN}  ALL CHECKS PASSED!${NC}"
echo "=============================================="
