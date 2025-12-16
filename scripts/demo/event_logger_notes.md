# Event Logger Analysis Notes

This document was created as part of implementing FR6/FR8 event logging.

## 1. GeoGuard Node

**File:** `ros2/src/sahtd_autonomy/sahtd_autonomy/control/geo_guard_node.py`

**Published Topics:**
| Topic | Type | Description |
|-------|------|-------------|
| `/gp2/guard/status` | String, TRANSIENT_LOCAL | `NORMAL`, `GEOGUARD_HOLD`, or `GEOGUARD_VIOLATION` |
| `/gp2/guard/reason` | String | Human-readable reason for state |
| `/gp2/guard/debug` | String | Single-line debug: `state=... enabled=... inside=... dist_m=...` |
| `/gp2/guard/distance_to_fence` | Float32 | Min distance to polygon edges |
| `/gp2/guard/inside` | Bool | Point-in-polygon result |

**Key function:** `_transition(self, new_state, reason)` is called on state changes.

---

## 2. Follow/Autonomy Topics

**File:** `ros2/src/sahtd_autonomy/sahtd_autonomy/control/follow_node.py`

**Published Topics:**
| Topic | Type | Description |
|-------|------|-------------|
| `/sahtd/follow/cmd_body` | Twist | Velocity command output |
| `/sahtd/follow/hud` | String | HUD debug string |
| `/sahtd/follow/seen_ids` | String | Visible track IDs |

**Subscribed Topics:**
| Topic | Type | Description |
|-------|------|-------------|
| `/perception/target_select` | Int32 | Manual target ID selection |
| `/perception/tracks` | Detection2DArray | ByteTrack outputs |
| `/gp2/guard/status` | String | Guard state for behavior adaptation |

**Follow States (from `state/fsm.py`):**
- `GROUND (0)` - On ground, waiting for takeoff
- `TAKEOFF (1)` - Taking off to target altitude
- `SEARCH (2)` - Airborne, searching for target
- `LOCKED (3)` - Tracking locked target

**Note:** Follow node does NOT currently publish a `/sahtd/follow/state` topic. The state is internal only.

---

## 3. Demo Orchestrator Scripts

### `scripts/demo/demo_committee.sh`
- **Subcommands:** `up`, `spawn`, `select`, `status`, `reset`
- **Options:** `--guard on|off`, `--markers on|off`, `--spawn`, `--autoselect`, `--policy best|first`, `--world`, `--timeout`
- **Session name:** `sahtd_stack`

### `scripts/demo/auto_select_target.py`
- Listens to `/perception/tracks` or `/sahtd/follow/seen_ids`
- Publishes to `/perception/target_select`
- Policy: `best` (largest bbox) or `first`

---

## 4. Web Backend Endpoints

**File:** `web/backend/app/main.py`

**Command Endpoints (POST):**
| Endpoint | Description |
|----------|-------------|
| `/cmd/pause` | Pause following |
| `/cmd/resume` | Resume following |
| `/cmd/rtl` | Return to launch |
| `/cmd/land` | Land immediately |

**WebSocket Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `/ws/state` | Live state stream (mock data currently) |
| `/ws/alerts` | Alerts stream |

**Note:** Currently these are mock endpoints, not wired to ROS.

---

## 5. Decision: What to Log

**From ROS nodes (runtime transitions):**
- `GUARD_NORMAL`, `GUARD_HOLD`, `GUARD_VIOLATION` - from `/gp2/guard/status` on transitions
- `TARGET_SELECTED` - from `/perception/target_select`

**From scripts (operator actions):**
- `ACTOR_SPAWNED` - when `demo_committee.sh spawn` is called
- `DEMO_RESET` - when `demo_committee.sh reset` is called

**Answer: Log from BOTH ROS nodes (for runtime) AND scripts (for operator actions).**

---

## 6. Topics That DON'T Exist Yet

- `/sahtd/follow/state` - Follow node state is internal only
- `/sahtd/follow/reason` - Not published

**Recommendation:** The event logger should subscribe to available topics only. Future enhancement could add state publishing to follow_node.

---

## 7. Log File Location

`~/sahtd/data/logs/events.jsonl`

Created automatically by the logger node. Each line is a JSON object.
