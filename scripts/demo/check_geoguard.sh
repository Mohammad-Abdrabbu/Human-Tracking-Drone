#!/bin/bash
# check_geoguard.sh - Pre-flight verification for geo_guard_node
# Usage: ./check_geoguard.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "  SAHTD GeoGuard Pre-Flight Check"
echo "=============================================="
echo ""

echo -e "${YELLOW}[1/6] Checking /gp2/guard/status...${NC}"
ros2 topic info -v /gp2/guard/status 2>&1 | head -10
echo ""

echo -e "${YELLOW}[2/6] Checking /gp2/guard/reason...${NC}"
ros2 topic info -v /gp2/guard/reason 2>&1 | head -10
echo ""

echo -e "${YELLOW}[3/6] Checking /gp2/guard/debug...${NC}"
ros2 topic info -v /gp2/guard/debug 2>&1 | head -10
echo ""

echo -e "${YELLOW}[4/6] Checking /sahtd/follow/cmd_body...${NC}"
ros2 topic info -v /sahtd/follow/cmd_body 2>&1 | head -10
echo ""

echo -e "${YELLOW}[5/6] Pose local publishing rate...${NC}"
timeout 3 ros2 topic hz /gp2/vehicle/pose_local 2>&1 || echo "Timeout"
echo ""

echo -e "${YELLOW}[6/6] Sampling status & reason (5s)...${NC}"
echo "--- /gp2/guard/status ---"
timeout 5 ros2 topic echo /gp2/guard/status --once 2>&1 || echo "No message"
echo ""
echo "--- /gp2/guard/reason ---"
timeout 5 ros2 topic echo /gp2/guard/reason --once 2>&1 || echo "No message"
echo ""

echo -e "${GREEN}Pre-flight check complete.${NC}"
