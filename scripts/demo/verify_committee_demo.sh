#!/usr/bin/env bash
# verify_committee_demo.sh - End-to-end verification of committee demo
# Tests the full flow including --policy best

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo ""
echo "=============================================="
echo "  SAHTD Committee Demo Verification"
echo "=============================================="
echo ""

# Step 1: Start demo with --policy best
echo -e "${YELLOW}[1/5] Starting demo with --policy best...${NC}"
"$SCRIPT_DIR/demo_committee.sh" up --guard on --spawn --autoselect --policy best || {
    echo -e "${RED}FAIL: Could not start demo${NC}"
    exit 1
}

# Step 2: Wait for things to settle
echo ""
echo -e "${YELLOW}[2/5] Waiting 5 seconds for system to settle...${NC}"
sleep 5

# Step 3: Check tracks
echo ""
echo -e "${YELLOW}[3/5] Checking /perception/tracks...${NC}"
TRACKS_HZ=$(timeout 3 ros2 topic hz /perception/tracks 2>&1 | grep "average rate" | tail -1 | awk '{print $3}' || echo "0")
if [ -n "$TRACKS_HZ" ] && [ "$TRACKS_HZ" != "0" ]; then
    echo -e "${GREEN}✓ Tracks publishing at ${TRACKS_HZ} Hz${NC}"
else
    echo -e "${RED}✗ Tracks not publishing${NC}"
fi

# Step 4: Check guard debug
echo ""
echo -e "${YELLOW}[4/5] Checking /gp2/guard/debug...${NC}"
DEBUG=$(timeout 3 ros2 topic echo /gp2/guard/debug --once 2>/dev/null | grep "data:" | sed 's/data: //' || echo "")
if [ -n "$DEBUG" ]; then
    echo -e "${GREEN}✓ Guard debug: $DEBUG${NC}"
else
    echo -e "${RED}✗ Guard debug not publishing${NC}"
fi

# Step 5: Test manual override
echo ""
echo -e "${YELLOW}[5/5] Testing manual override...${NC}"
ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: 99}' --once 2>/dev/null && \
    echo -e "${GREEN}✓ Manual override published (id=99)${NC}" || \
    echo -e "${RED}✗ Manual override failed${NC}"

echo ""
echo "=============================================="
echo -e "${GREEN}  VERIFICATION COMPLETE${NC}"
echo "=============================================="
echo ""
echo "Key output to look for:"
echo "  'Selected id=X policy=best area=YYYY'"
echo ""
echo "To monitor: ros2 topic echo /gp2/guard/debug"
echo ""
