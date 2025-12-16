# SAHTD Committee Demo Guide

Quick reference for running the human-tracking drone demo at technical checkpoint.

---

## Quick Start (5 Steps)

```bash
# 1. Reset everything (clean slate)
~/sahtd/scripts/demo/demo_committee.sh reset

# 2. Start the full stack with guard + spawn + autoselect
~/sahtd/scripts/demo/demo_committee.sh up --guard on --spawn --autoselect

# 3. (Wait for "DEMO READY" message)

# 4. Monitor guard status during demo
ros2 topic echo /gp2/guard/debug

# 5. When done, reset
~/sahtd/scripts/demo/demo_committee.sh reset
```

---

## Full Command Reference

### Start Demo
```bash
# Full demo with all features
demo_committee.sh up --guard on --spawn --autoselect

# Track-only (no geofence)
demo_committee.sh up --guard off --spawn --autoselect

# Manual target selection (no autoselect)
demo_committee.sh up --guard on --spawn
```

### Spawn Actor Manually
```bash
demo_committee.sh spawn
```

### Select Target Manually
```bash
# Auto-select largest target
demo_committee.sh select --policy best

# Or publish directly
ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: 1}' --once
```

### Check Status
```bash
demo_committee.sh status
```

### Reset/Cleanup
```bash
demo_committee.sh reset
```

---

## Expected Outputs

### After `up --spawn --autoselect`
```
════════════════════════════════════════════════════════════
  SAHTD Committee Demo Orchestrator
════════════════════════════════════════════════════════════

✓ Stack already running
  Checking /gp2/vehicle/pose_local... ✓
  Checking /gp2/guard/status... ✓
  Checking /perception/tracks... ✓

✓ Geofence enabled (default)
Selected target id=1 using policy=best

╔══════════════════════════════════════════════════════════╗
║                     DEMO READY                           ║
╚══════════════════════════════════════════════════════════╝
```

### Guard Debug Output
```
state=NORMAL enabled=true inside=true dist_m=5.23 soft_m=0.80 hard_m=0.30 pose=(x=2.1,y=-0.5) nearest_edge=0
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Topics not publishing | `demo_committee.sh reset` then try again |
| PX4 not connecting | Check `tmux attach -t sahtd_stack` top pane |
| Actor not visible | Verify camera is working: `ros2 topic hz /camera/image_raw` |
| No tracks | YOLO may need warmup; wait 5-10s |

---

## Verification Script
```bash
~/sahtd/scripts/demo/verify_committee_demo.sh
```
