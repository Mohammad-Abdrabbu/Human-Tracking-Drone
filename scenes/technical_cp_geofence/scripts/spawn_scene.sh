#!/bin/bash
# spawn_scene.sh - Spawns actors for Technical CP Geofence scene
# Safe to run multiple times (idempotent)

set -e

# Resolve paths
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCENE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAHTD_ROOT="$(cd "$SCENE_DIR/../.." && pwd)"

WORLD_NAME="technical_cp_geofence"

# Set GZ_SIM_RESOURCE_PATH for model:// resolution
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+$GZ_SIM_RESOURCE_PATH:}$SAHTD_ROOT/simulation/models"

echo "[spawn_scene] Checking if Gazebo world is ready..."
echo "[spawn_scene] GZ_SIM_RESOURCE_PATH: $GZ_SIM_RESOURCE_PATH"

# Wait for Gazebo world to be available (up to 30 seconds)
MAX_WAIT=30
WAITED=0
while ! gz topic -l 2>/dev/null | grep -q "/world/${WORLD_NAME}"; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[spawn_scene] ERROR: Gazebo world '${WORLD_NAME}' not found after ${MAX_WAIT}s"
        echo "[spawn_scene] Make sure PX4 SITL is running with: PX4_GZ_WORLD=${WORLD_NAME} ./scripts/core/start_px4.sh"
        exit 1
    fi
    echo "[spawn_scene] Waiting for world '${WORLD_NAME}'... (${WAITED}s)"
    sleep 2
    WAITED=$((WAITED + 2))
done

echo "[spawn_scene] World is ready!"
echo "[spawn_scene] Actors should be embedded in the world SDF."
echo "[spawn_scene] Expected actors: person_violator, person_walk_inside, person_stand_1-4"

# Verify actors exist
for ACTOR in person_violator person_stand_1; do
    if gz model -m ${ACTOR} --world ${WORLD_NAME} 2>/dev/null | grep -q "pose"; then
        echo "[spawn_scene] ✓ Actor '${ACTOR}' found"
    else
        echo "[spawn_scene] ⚠ Actor '${ACTOR}' not found (may still be loading)"
    fi
done

echo "[spawn_scene] Scene ready!"
