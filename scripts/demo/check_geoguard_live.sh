#!/bin/bash
# check_geoguard_live.sh - Live demo verification for committee checkpoint
# Usage: ./check_geoguard_live.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=============================================="
echo "  SAHTD GeoGuard Live Demo Check"
echo "=============================================="
echo ""

echo -e "${YELLOW}[1/4] Debug topic publishing rate...${NC}"
timeout 5 ros2 topic hz /gp2/guard/debug 2>&1 || echo "Timeout - check if geo_guard_node is running"
echo ""

echo -e "${YELLOW}[2/4] Distance to fence rate...${NC}"
timeout 3 ros2 topic hz /gp2/guard/distance_to_fence 2>&1 || echo "Timeout"
echo ""

echo -e "${YELLOW}[3/4] Sample debug output...${NC}"
echo -e "${CYAN}"
timeout 5 ros2 topic echo /gp2/guard/debug --once 2>&1 || echo "No message"
echo -e "${NC}"

echo -e "${YELLOW}[4/4] Sample distance output...${NC}"
timeout 3 ros2 topic echo /gp2/guard/distance_to_fence --once 2>&1 || echo "No message"
echo ""

echo "=============================================="
echo -e "${GREEN}Live check complete.${NC}"
echo ""
echo "To monitor continuously:"
echo "  ros2 topic echo /gp2/guard/debug"
echo ""
