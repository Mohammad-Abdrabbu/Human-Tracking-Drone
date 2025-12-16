# Report: One-Click Demo Orchestrator

## Overview
Created a single-command demo orchestrator for the SAHTD technical checkpoint.

---

## New Scripts

| Script | Purpose |
|--------|---------|
| `scripts/demo/demo_committee.sh` | Main orchestrator with subcommands |
| `scripts/demo/auto_select_target.py` | Auto-select first visible target |
| `scripts/demo/README_DEMO.md` | Quick reference guide |
| `scripts/demo/verify_committee_demo.sh` | Verification script |

---

## Usage

```bash
# Full demo: start stack + spawn actor + auto-select target
demo_committee.sh up --guard on --spawn --autoselect

# Check status
demo_committee.sh status

# Reset everything
demo_committee.sh reset
```

---

## Subcommands

| Command | Description |
|---------|-------------|
| `up` | Start stack, wait for topics, configure guard |
| `spawn` | Spawn actor in Gazebo (waits for world ready) |
| `select` | Auto-select target from visible IDs |
| `status` | Print system status |
| `reset` | Stop all services and clean up |

---

## Features

1. **Guard Toggle**: `--guard on|off` enables/disables geofence via `guard_enabled` param
2. **Auto Spawn**: `--spawn` spawns slow walker actor, waits for Gazebo ready
3. **Auto Select**: `--autoselect` selects first visible target from `/sahtd/follow/seen_ids`
4. **Topic Checks**: Verifies critical topics before reporting READY

---

## Commit Message
```
Add committee demo orchestrator + auto-select + guard toggle
```
