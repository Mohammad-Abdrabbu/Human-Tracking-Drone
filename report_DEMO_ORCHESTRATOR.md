# Report: Demo Orchestrator + Auto-Select Enhancement

## Overview
Created a one-click demo orchestrator with intelligent auto-select for the SAHTD technical checkpoint.

---

## Files Modified/Created

| File | Status | Description |
|------|--------|-------------|
| `scripts/demo/demo_committee.sh` | Modified | Added `--policy` option for auto-select |
| `scripts/demo/auto_select_target.py` | Modified | Implemented `best` and `first` policies |
| `scripts/demo/README_DEMO.md` | Modified | Updated with policy documentation |
| `scripts/demo/verify_committee_demo.sh` | Modified | Uses `--policy best` for testing |

---

## Auto-Select Policies

| Policy | Behavior |
|--------|----------|
| `best` (default) | Subscribe to `/perception/tracks`, select detection with **largest bbox area** (`size_x × size_y`), publish ID once |
| `first` | Read first ID from `/sahtd/follow/seen_ids`, fallback to first detection in tracks |

### Key Requirements Met
- ✅ Publishes to `/perception/target_select` **once only**
- ✅ Manual override via `/perception/target_select` takes effect immediately after
- ✅ Exits cleanly after selection or timeout

---

## Usage

### Recommended Command
```bash
~/sahtd/scripts/demo/demo_committee.sh up --guard on --spawn --autoselect --policy best
```

### All Options
```bash
# Full demo with largest target (recommended)
demo_committee.sh up --guard on --spawn --autoselect --policy best

# Full demo with first visible target
demo_committee.sh up --guard on --spawn --autoselect --policy first

# Without explicit policy (defaults to best)
demo_committee.sh up --guard on --spawn --autoselect

# Manual selection commands
demo_committee.sh select --policy best --timeout 10
demo_committee.sh select --policy first
```

---

## Verified Output

```
Auto-selecting target (policy: best, timeout: 10s)...
[INFO] [auto_select_target]: Policy=best: waiting for tracks on /perception/tracks
[INFO] [auto_select_target]: Selected id=1 policy=best area=2114
```

### Manual Override Test
After auto-select, manual override works immediately:
```bash
ros2 topic pub /perception/target_select std_msgs/msg/Int32 '{data: 5}' --once
```

---

## Technical Details

### auto_select_target.py CLI
```
--policy best|first     Selection policy (default: best)
--timeout <sec>         Timeout in seconds (default: 5)
--tracks-topic          Tracks topic (default: /perception/tracks)
--seen-ids-topic        Seen IDs topic (default: /sahtd/follow/seen_ids)
--select-topic          Selection topic (default: /perception/target_select)
```

### ID Extraction Logic
1. Try `int(detection.results[0].hypothesis.class_id)`
2. Fallback: extract digits from string with regex `(\d+)`

---

## Commit Message
```
Enhance auto-select with best/first policies for committee demo
```
