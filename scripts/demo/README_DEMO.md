# SAHTD Committee Demo Guide

Quick reference for running the human-tracking drone demo at technical checkpoint.

---

## Quick Start (Recommended)

```bash
# Full demo with best policy (selects largest target)
~/sahtd/scripts/demo/demo_committee.sh up --guard on --spawn --autoselect --policy best
```

---

## All Commands

### Start Demo
```bash
# Full demo with largest target (recommended)
demo_committee.sh up --guard on --spawn --autoselect --policy best

# Full demo with first visible target
demo_committee.sh up --guard on --spawn --autoselect --policy first

# Track-only (no geofence)
demo_committee.sh up --guard off --spawn --autoselect

# Manual target selection
demo_committee.sh up --guard on --spawn
```

### Individual Commands
```bash
demo_committee.sh spawn              # Spawn actor
demo_committee.sh select --policy best   # Auto-select largest
demo_committee.sh select --policy first  # Auto-select first
demo_committee.sh status             # Check status
demo_committee.sh reset              # Reset everything
```

### Manual Target Override
```bash
ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: 5}' --once
```

---

## Auto-Select Policies

| Policy | Behavior |
|--------|----------|
| `best` | Subscribe to `/perception/tracks`, select detection with **largest bbox area** |
| `first` | Select first ID from `/sahtd/follow/seen_ids` (or first track) |

---

## Expected Output

```
Auto-selecting target (policy: best, timeout: 10s)...
Selected id=1 policy=best area=12500
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No targets found | Ensure actor is spawned and visible to camera |
| Wrong target selected | Use manual override: `ros2 topic pub ...` |
| Guard blocking movement | Check `ros2 topic echo /gp2/guard/debug` |
