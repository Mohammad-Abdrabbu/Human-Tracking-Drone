#!/usr/bin/env bash
##
# Lane B Phase 2: Bag Info Helper
# ================================
# Quick tool to inspect bag files.
#
# Usage:
#   ./scripts/sahtd_bag_info.sh <bag_name_or_path>
#   ./scripts/sahtd_bag_info.sh                     # list bags
##

set -e

# Resolve SAHTD_ROOT as the repo root (…/gp2)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SAHTD_ROOT

BAGS_DIR="$SAHTD_ROOT/bags/follow"

if [ $# -eq 0 ]; then
  echo "Usage: $0 <bag_name_or_path>"
  echo ""
  if [ -d "$BAGS_DIR" ]; then
    echo "Available bags in $BAGS_DIR:"
    ls -1dt "$BAGS_DIR"/B_follow_* 2>/dev/null | head -10 || echo "  (none found)"
  else
    echo "Bags directory not found: $BAGS_DIR"
  fi
  exit 0
fi

BAG_PATH="$1"

# If path doesn't exist, try appending bags dir
if [ ! -e "$BAG_PATH" ]; then
  if [ -e "$BAGS_DIR/$BAG_PATH" ]; then
    BAG_PATH="$BAGS_DIR/$BAG_PATH"
  fi
fi

# Run ros2 bag info
if [ -e "$BAG_PATH" ]; then
  ros2 bag info "$BAG_PATH"
else
  echo "Error: Bag not found: $BAG_PATH"
  exit 1
fi
