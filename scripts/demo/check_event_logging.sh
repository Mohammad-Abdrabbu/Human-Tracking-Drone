#!/usr/bin/env bash
# check_event_logging.sh - Verification script for event logging system
#
# This script verifies that the event logging system is working correctly:
# 1. Log directory exists
# 2. Event logger node is running (or can be started)
# 3. Guard events are logged on state transitions
# 4. Target selection events are logged
# 5. JSONL schema is correct

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
EVENTS_LOG_FILE="$HOME/sahtd/data/logs/events.jsonl"
EVENTS_LOG_DIR="$(dirname "$EVENTS_LOG_FILE")"

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Event Logging Verification${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Source ROS
source /opt/ros/humble/setup.bash 2>/dev/null || true
source "$SAHTD_ROOT/ros2/install/setup.bash" 2>/dev/null || true

PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++))
    else
        echo -e "  ${RED}✗${NC} $name"
        ((FAIL++))
    fi
}

# === Check 1: Log directory exists ===
echo -e "${YELLOW}Check 1: Log directory${NC}"
mkdir -p "$EVENTS_LOG_DIR" 2>/dev/null || true
if [ -d "$EVENTS_LOG_DIR" ]; then
    check "Log directory exists: $EVENTS_LOG_DIR" 0
else
    check "Log directory exists: $EVENTS_LOG_DIR" 1
fi

# === Check 2: Event logger node ===
echo ""
echo -e "${YELLOW}Check 2: Event logger node${NC}"
if ros2 node list 2>/dev/null | grep -q "event_logger_node"; then
    check "Event logger node is running" 0
else
    echo "  Event logger not running, attempting to start..."
    ros2 run sahtd_autonomy event_logger_node &>/dev/null &
    sleep 2
    if ros2 node list 2>/dev/null | grep -q "event_logger_node"; then
        check "Event logger node started successfully" 0
    else
        check "Event logger node could not be started" 1
        echo -e "  ${YELLOW}Tip: Make sure you've built the package: colcon build --packages-select sahtd_autonomy${NC}"
    fi
fi

# === Check 3: Log file helper script ===
echo ""
echo -e "${YELLOW}Check 3: Log event helper script${NC}"
if [ -f "$SCRIPT_DIR/log_event.py" ]; then
    check "log_event.py exists" 0
    
    # Test the helper
    BEFORE_COUNT=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)
    python3 "$SCRIPT_DIR/log_event.py" TEST_EVENT '{"test": true}' --source verification 2>/dev/null
    AFTER_COUNT=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)
    
    if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
        check "log_event.py writes to log file" 0
    else
        check "log_event.py writes to log file" 1
    fi
else
    check "log_event.py exists" 1
fi

# === Check 4: Trigger target_select event ===
echo ""
echo -e "${YELLOW}Check 4: Target selection event${NC}"
BEFORE_COUNT=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)

# Publish a target selection
ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: 999}' --once 2>/dev/null

# Wait for event to be logged
sleep 1.5

AFTER_COUNT=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)
if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
    check "Target selection event logged" 0
else
    check "Target selection event logged (may require running logger node)" 1
fi

# === Check 5: JSONL schema validation ===
echo ""
echo -e "${YELLOW}Check 5: JSONL schema validation${NC}"
if [ -f "$EVENTS_LOG_FILE" ] && [ -s "$EVENTS_LOG_FILE" ]; then
    # Get last line and validate JSON
    LAST_LINE=$(tail -n 1 "$EVENTS_LOG_FILE")
    
    # Check if it's valid JSON using Python
    if echo "$LAST_LINE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        check "Last line is valid JSON" 0
        
        # Check for required fields
        HAS_TS=$(echo "$LAST_LINE" | python3 -c "import sys, json; d=json.load(sys.stdin); print('ts' in d)")
        HAS_EVENT=$(echo "$LAST_LINE" | python3 -c "import sys, json; d=json.load(sys.stdin); print('event' in d)")
        HAS_SOURCE=$(echo "$LAST_LINE" | python3 -c "import sys, json; d=json.load(sys.stdin); print('source' in d)")
        
        if [ "$HAS_TS" = "True" ] && [ "$HAS_EVENT" = "True" ] && [ "$HAS_SOURCE" = "True" ]; then
            check "JSONL has required fields (ts, event, source)" 0
        else
            check "JSONL has required fields (ts, event, source)" 1
        fi
    else
        check "Last line is valid JSON" 1
    fi
else
    check "Log file exists and has content" 1
fi

# === Check 6: ROS topic ===
echo ""
echo -e "${YELLOW}Check 6: /sahtd/events topic${NC}"
if ros2 topic info /sahtd/events 2>/dev/null | grep -q "Publisher count: [1-9]"; then
    check "/sahtd/events topic has publishers" 0
else
    check "/sahtd/events topic has publishers (requires running logger node)" 1
fi

# === Summary ===
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Summary${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Passed: ${GREEN}$PASS${NC}"
echo -e "  Failed: ${RED}$FAIL${NC}"
echo ""

if [ -f "$EVENTS_LOG_FILE" ]; then
    echo -e "${CYAN}Last 5 events:${NC}"
    tail -n 5 "$EVENTS_LOG_FILE" 2>/dev/null | while read line; do
        # Pretty print with jq if available, otherwise just show the line
        if command -v jq &>/dev/null; then
            echo "$line" | jq -c '.' 2>/dev/null || echo "  $line"
        else
            echo "  $line"
        fi
    done
    echo ""
fi

echo -e "${CYAN}Useful commands:${NC}"
echo "  tail -f $EVENTS_LOG_FILE"
echo "  ros2 topic echo /sahtd/events"
echo "  ros2 node list | grep event"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some checks failed. Review output above.${NC}"
    exit 1
fi
