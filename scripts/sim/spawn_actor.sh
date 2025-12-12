#!/usr/bin/env bash
##
# SAHTD Actor Spawn Helper
# ========================
# Simplified one-liner commands to spawn human actors in Gazebo.
#
# Usage:
#   ./scripts/sahtd_spawn_actor.sh <actor_type> [x] [y] [z] [name]
#
# Actor types:
#   walk     - Walking actor (medium speed, S-curve)
#   slow     - Slow walking actor
#   fast     - Fast walking actor
#   toward   - Walk toward drone
#   sideways - Sideways sweep
#   stand    - Static standing human (Casual female)
#
# Examples:
#   ./scripts/sahtd_spawn_actor.sh walk              # Spawn at (3,0,1)
#   ./scripts/sahtd_spawn_actor.sh walk 5 2 1        # Spawn at (5,2,1)
#   ./scripts/sahtd_spawn_actor.sh walk 3 0 1 bob    # Named "bob"
##

set -e

# Resolve SAHTD_ROOT as the repo root (scripts/sim/spawn_actor.sh → ../..)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

MODELS_DIR="$SAHTD_ROOT/simulation/models"

# Parse arguments
ACTOR_TYPE="${1:-walk}"
X="${2:-3.0}"
Y="${3:-0.0}"
Z="${4:-1.0}"

# Default names based on type
case "$ACTOR_TYPE" in
    walk)
        MODEL_PATH="$MODELS_DIR/actor_walk/model.sdf"
        DEFAULT_NAME="human_walk"
        ;;
    slow)
        MODEL_PATH="$MODELS_DIR/actor_walk_slow/model.sdf"
        DEFAULT_NAME="human_walk_slow"
        ;;
    fast)
        MODEL_PATH="$MODELS_DIR/actor_walk_fast/model.sdf"
        DEFAULT_NAME="human_walk_fast"
        ;;
    toward)
        MODEL_PATH="$MODELS_DIR/actor_toward/model.sdf"
        DEFAULT_NAME="human_toward"
        ;;
    sideways)
        MODEL_PATH="$MODELS_DIR/actor_sideways/model.sdf"
        DEFAULT_NAME="human_sideways"
        ;;
    stand)
        MODEL_PATH="$MODELS_DIR/Casual female/model.sdf"
        DEFAULT_NAME="human_stand"
        ;;
    *)
        echo "Error: Unknown actor type '$ACTOR_TYPE'"
        echo "Valid types: walk, slow, fast, toward, sideways, stand"
        exit 1
        ;;
esac

NAME="${5:-$DEFAULT_NAME}"

# Check model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model not found: $MODEL_PATH"
    exit 1
fi

echo "========================================"
echo "Spawning Actor"
echo "========================================"
echo "Type:     $ACTOR_TYPE"
echo "Model:    $MODEL_PATH"
echo "Name:     $NAME"
echo "Position: ($X, $Y, $Z)"
echo "========================================"

# Call gz service
gz service -s /world/default/create \
    --reqtype gz.msgs.EntityFactory \
    --reptype gz.msgs.Boolean \
    --timeout 5000 \
    --req "sdf_filename: \"$MODEL_PATH\", name: \"$NAME\", allow_renaming: false, pose: {position: {x: $X, y: $Y, z: $Z}}"

echo ""
echo "✓ Actor spawned successfully"
