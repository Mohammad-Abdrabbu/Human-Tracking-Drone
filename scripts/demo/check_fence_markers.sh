#!/usr/bin/env bash
# check_fence_markers.sh - Verify geo-fence marker spawning works correctly
#
# Runs through the complete marker workflow:
# 1. Dry-run to show planned markers
# 2. Spawn markers
# 3. Verify markers exist in Gazebo
#
# Usage:
#   ./check_fence_markers.sh [--world NAME]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPAWN_SCRIPT="$SCRIPT_DIR/spawn_fence_markers.py"

# Defaults
WORLD="default"
PREFIX="fence_marker"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --world) WORLD="$2"; shift 2 ;;
        --prefix) PREFIX="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--world NAME] [--prefix PREFIX]"
            exit 0
            ;;
        *) shift ;;
    esac
done

echo -e "${CYAN}=== Geo-Fence Marker Verification ===${NC}"
echo ""

# Step 1: Dry-run
echo -e "${YELLOW}Step 1: Dry-run (showing planned markers)${NC}"
echo "----------------------------------------"
python3 "$SPAWN_SCRIPT" --world "$WORLD" --prefix "$PREFIX" --dry-run
echo ""

# Count expected vertices from dry-run output
EXPECTED_COUNT=$(python3 "$SPAWN_SCRIPT" --dry-run 2>/dev/null | grep "^  ${PREFIX}_v" | wc -l)
echo -e "${CYAN}Expected marker count: $EXPECTED_COUNT${NC}"
echo ""

# Step 2: Spawn markers
echo -e "${YELLOW}Step 2: Spawning markers${NC}"
echo "----------------------------------------"
python3 "$SPAWN_SCRIPT" --world "$WORLD" --prefix "$PREFIX"
echo ""

# Step 3: Verify markers exist
echo -e "${YELLOW}Step 3: Verifying markers in Gazebo${NC}"
echo "----------------------------------------"

# Give Gazebo a moment to register the models
sleep 1

# List all models matching prefix
FOUND_MODELS=$(gz model --list --world "$WORLD" 2>/dev/null | grep "^${PREFIX}_v" || true)
FOUND_COUNT=$(echo "$FOUND_MODELS" | grep -c "^${PREFIX}_v" || echo "0")

echo "Found models:"
if [ -n "$FOUND_MODELS" ]; then
    echo "$FOUND_MODELS" | while read model; do
        echo -e "  ${GREEN}✓${NC} $model"
    done
else
    echo -e "  ${RED}(none)${NC}"
fi
echo ""

# Step 4: Idempotency check
echo -e "${YELLOW}Step 4: Idempotency check (running spawn again)${NC}"
echo "----------------------------------------"
python3 "$SPAWN_SCRIPT" --world "$WORLD" --prefix "$PREFIX"
echo ""

# Final count
FINAL_MODELS=$(gz model --list --world "$WORLD" 2>/dev/null | grep "^${PREFIX}_v" || true)
FINAL_COUNT=$(echo "$FINAL_MODELS" | grep -c "^${PREFIX}_v" || echo "0")

# Results
echo -e "${CYAN}=== Results ===${NC}"
echo ""

PASS=true

# Check 1: Marker count matches vertex count
if [ "$FINAL_COUNT" -eq "$EXPECTED_COUNT" ] 2>/dev/null; then
    echo -e "${GREEN}✓ Marker count matches vertex count ($FINAL_COUNT == $EXPECTED_COUNT)${NC}"
else
    echo -e "${RED}✗ Marker count mismatch ($FINAL_COUNT != $EXPECTED_COUNT)${NC}"
    PASS=false
fi

# Check 2: No duplicates (count didn't increase on second run)
if [ "$FINAL_COUNT" -eq "$FOUND_COUNT" ] 2>/dev/null; then
    echo -e "${GREEN}✓ Idempotency OK (no duplicates created)${NC}"
else
    echo -e "${RED}✗ Duplicates detected ($FINAL_COUNT != $FOUND_COUNT)${NC}"
    PASS=false
fi

echo ""

if [ "$PASS" = true ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      ALL CHECKS PASSED                ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════╗${NC}"
    echo -e "${RED}║      SOME CHECKS FAILED               ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════╝${NC}"
    exit 1
fi
