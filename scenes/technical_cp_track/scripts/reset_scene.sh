#!/bin/bash
# reset_scene.sh - Resets the Technical CP Track scene
# Removes the actor and respawns it at starting position

set -e

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"

WORLD_NAME="technical_cp_track"
ACTOR_NAME="person_track"
ACTOR_SDF="$SCENE_DIR/actors/person_track.sdf"

# Set GZ_SIM_RESOURCE_PATH for model:// resolution
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+$GZ_SIM_RESOURCE_PATH:}$SAHTD_ROOT/simulation/models"

echo "[reset_scene] Resetting scene for world: ${WORLD_NAME}"
echo "[reset_scene] GZ_SIM_RESOURCE_PATH includes: $SAHTD_ROOT/simulation/models"

# Check if world is running
if ! gz topic -l 2>/dev/null | grep -q "/world/${WORLD_NAME}"; then
    echo "[reset_scene] ERROR: World '${WORLD_NAME}' is not running."
    echo "[reset_scene] Start with: PX4_GZ_WORLD=${WORLD_NAME} ./scripts/core/start_px4.sh"
    exit 1
fi

# Try to remove existing actor
echo "[reset_scene] Attempting to remove actor '${ACTOR_NAME}'..."
gz service -s /world/${WORLD_NAME}/remove \
    --reqtype gz.msgs.Entity \
    --reptype gz.msgs.Boolean \
    --timeout 3000 \
    --req "name: '${ACTOR_NAME}', type: MODEL" 2>/dev/null || true

sleep 1

# Respawn the actor
echo "[reset_scene] Respawning actor..."
if [ -f "${ACTOR_SDF}" ]; then
    gz service -s /world/${WORLD_NAME}/create \
        --reqtype gz.msgs.EntityFactory \
        --reptype gz.msgs.Boolean \
        --timeout 5000 \
        --req "sdf_filename: '${ACTOR_SDF}'" || {
            echo "[reset_scene] Note: Actor may already be embedded in world SDF"
        }
else
    echo "[reset_scene] WARNING: Actor SDF not found at: ${ACTOR_SDF}"
fi

echo "[reset_scene] Reset complete!"
