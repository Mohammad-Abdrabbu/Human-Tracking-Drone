#!/bin/bash
# reset_scene.sh - Resets the Technical CP Geofence scene
# Note: Removes violator and respawns to restart violation sequence

set -e

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"

WORLD_NAME="technical_cp_geofence"
VIOLATOR_SDF="$SCENE_DIR/actors/person_violator.sdf"

# Set GZ_SIM_RESOURCE_PATH for model:// resolution
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+$GZ_SIM_RESOURCE_PATH:}$SAHTD_ROOT/simulation/models"

echo "[reset_scene] Resetting scene for world: ${WORLD_NAME}"

# Check if world is running
if ! gz topic -l 2>/dev/null | grep -q "/world/${WORLD_NAME}"; then
    echo "[reset_scene] ERROR: World '${WORLD_NAME}' is not running."
    echo "[reset_scene] Start with: PX4_GZ_WORLD=${WORLD_NAME} ./scripts/core/start_px4.sh"
    exit 1
fi

# Remove the violator actor
echo "[reset_scene] Removing 'person_violator'..."
gz service -s /world/${WORLD_NAME}/remove \
    --reqtype gz.msgs.Entity \
    --reptype gz.msgs.Boolean \
    --timeout 3000 \
    --req "name: 'person_violator', type: MODEL" 2>/dev/null || true

sleep 1

# Respawn the violator
echo "[reset_scene] Respawning 'person_violator'..."
if [ -f "${VIOLATOR_SDF}" ]; then
    gz service -s /world/${WORLD_NAME}/create \
        --reqtype gz.msgs.EntityFactory \
        --reptype gz.msgs.Boolean \
        --timeout 5000 \
        --req "sdf_filename: '${VIOLATOR_SDF}'" || {
            echo "[reset_scene] Warning: Could not respawn violator"
        }
    echo "[reset_scene] ✓ Violator respawned - violation sequence will restart"
else
    echo "[reset_scene] ERROR: Violator SDF not found at: ${VIOLATOR_SDF}"
fi

echo "[reset_scene] Reset complete!"
