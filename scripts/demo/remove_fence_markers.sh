#!/usr/bin/env bash
# remove_fence_markers.sh - Remove all geo-fence markers from Gazebo
#
# Usage:
#   ./remove_fence_markers.sh [--world NAME] [--prefix PREFIX]
#
# Safe to run even if no markers exist.

set -e

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
            echo "  --world   Gazebo world name (default: default)"
            echo "  --prefix  Marker name prefix (default: fence_marker)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "=== Geo-Fence Marker Cleanup ==="
echo "  World:  $WORLD"
echo "  Prefix: $PREFIX"
echo ""

# Get list of models matching prefix
MODELS=$(gz model --list --world "$WORLD" 2>/dev/null | grep "^${PREFIX}" || true)

if [ -z "$MODELS" ]; then
    echo "No markers found with prefix '$PREFIX'"
    exit 0
fi

echo "Removing markers:"

# Remove each model
for model in $MODELS; do
    echo -n "  $model: "
    if gz service -s "/world/$WORLD/remove" \
        --reqtype gz.msgs.Entity \
        --reptype gz.msgs.Boolean \
        --timeout 3000 \
        --req "name: \"$model\", type: 2" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (may already be gone)"
    fi
done

echo ""
echo "Cleanup complete"
