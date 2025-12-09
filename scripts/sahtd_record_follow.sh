#!/usr/bin/env bash
##
# Lane B Phase 2: Follower Bag Recording Script
# ==============================================
# Records key topics for follower tuning analysis.
#
# Usage:
#   ./scripts/sahtd_record_follow.sh [SCENARIO_TAG]
#
# Examples:
#   ./scripts/sahtd_record_follow.sh W2
#   ./scripts/sahtd_record_follow.sh T1
#   ./scripts/sahtd_record_follow.sh     # defaults to GEN
#
# Output:
#   Bag saved to ~/gp2/bags/follow/B_follow_<TAG>_<TIMESTAMP>/
##

set -e

# Get scenario tag (default: GEN)
SCENARIO_TAG="${1:-GEN}"

# Create bags directory
BAGS_DIR="$HOME/gp2/bags/follow"
mkdir -p "$BAGS_DIR"

# Generate timestamped bag name
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BAG_NAME="B_follow_${SCENARIO_TAG}_${TIMESTAMP}"

# Topics to record
TOPICS=(
  "/perception/tracks"
  "/perception/target_select"
  "/perception/debug_image_tracks"
  "/gp2/follow/cmd_body"
  "/gp2/follow/hud"
  "/gp2/follow/seen_ids"
  "/gp2/guard/status"
  "/gp2/vehicle/pose_local"
)

# Print summary
echo "========================================"
echo "Lane B Phase 2: Follower Bag Recording"
echo "========================================"
echo "Target directory: $BAGS_DIR"
echo "Bag name:         $BAG_NAME"
echo "Scenario tag:     $SCENARIO_TAG"
echo ""
echo "Recording topics:"
for topic in "${TOPICS[@]}"; do
  echo "  - $topic"
done
echo ""
echo "Press Ctrl+C to stop recording."
echo "========================================"
echo ""

# Change to bags directory
cd "$BAGS_DIR"

# Run ros2 bag record
ros2 bag record \
  -o "$BAG_NAME" \
  "${TOPICS[@]}"
