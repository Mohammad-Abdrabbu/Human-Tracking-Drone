#!/bin/bash
# start_px4_fitexpo.sh
set -e

# Default to "sahtd_stack_expo" session if not set, though this script is primarily
# called by systemd or demo_fitexpo.sh which manages sessions.
export SAHTD_ROOT=${SAHTD_ROOT:-$HOME/sahtd}

# Use the same start_px4.sh core logic but we might need to override world if needed.
# For now, we use default world but with our custom objects spawned later.
# If headless is set, passed through.

# Ensuring we are in correct dir
cd $SAHTD_ROOT

# Map configuration (HEADLESS -> SAHTD_HEADLESS)
export SAHTD_HEADLESS=${HEADLESS:-0}

# Just call the core script for now. 
# If we needed a custom world file, we would pass commands to gz here.
exec ./scripts/core/start_px4.sh
