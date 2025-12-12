#!/usr/bin/env bash
##
# SAHTD Actor Delete Helper
# =========================
# Remove spawned actors from Gazebo.
#
# Usage:
#   ./scripts/sahtd_delete_actor.sh <actor_name>
#
# Examples:
#   ./scripts/sahtd_delete_actor.sh human_walk_ctrl
#   ./scripts/sahtd_delete_actor.sh human_walk
##

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <actor_name>"
    echo ""
    echo "Examples:"
    echo "  $0 human_walk_ctrl"
    echo "  $0 human_walk"
    exit 1
fi

NAME="$1"

echo "Deleting actor: $NAME"

gz service -s /world/default/remove \
    --reqtype gz.msgs.Entity \
    --reptype gz.msgs.Boolean \
    --timeout 3000 \
    --req "name: \"$NAME\", type: 2"

echo "✓ Actor deleted"
