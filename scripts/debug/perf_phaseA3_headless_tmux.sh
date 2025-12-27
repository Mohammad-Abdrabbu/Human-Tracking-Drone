#!/usr/bin/env bash
##############################################################################
# perf_phaseA3_headless_tmux.sh - Phase A3 Performance Logger
##############################################################################
#
# Simple background logger for ROS/GPU/CPU metrics. No tmux, no sync issues.
# All loggers run in parallel as background processes.
#
# USAGE:
#   1. Start your demo stack normally
#   2. ./scripts/debug/perf_phaseA3_headless_tmux.sh start
#   3. Let it run for as long as you want (data logged continuously)
#   4. ./scripts/debug/perf_phaseA3_headless_tmux.sh stop
#   5. View the report
#
# OUTPUT: ~/sahtd/data/perf/phaseA3_YYYYMMDD_HHMMSS/
#
##############################################################################

set -eo pipefail

# === Colors ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# === Paths ===
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

PERF_BASE_DIR="$SAHTD_ROOT/data/perf"
EVENTS_LOG_FILE="$SAHTD_ROOT/data/logs/events.jsonl"

# State files
STATE_DIR="/tmp/sahtd_perfA3"
STATE_FILE="$STATE_DIR/rundir"
PID_FILE="$STATE_DIR/pids"

# === Helper Functions ===

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  SAHTD Phase A3 Performance Logger${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_usage() {
    cat << 'EOF'
Usage:
  perf_phaseA3_headless_tmux.sh start [--duration <sec>]
  perf_phaseA3_headless_tmux.sh stop
  perf_phaseA3_headless_tmux.sh status

Commands:
  start   Start background loggers (GPU, CPU, ROS topics)
  stop    Stop all loggers and generate report
  status  Check if logging is active

Options:
  --duration <sec>   Auto-stop after N seconds (default: unlimited)

Workflow:
  1. Start demo: ./scripts/demo/demo_committee.sh up --spawn
  2. Start logger: ./scripts/debug/perf_phaseA3_headless_tmux.sh start
  3. Wait as long as you want...
  4. Stop: ./scripts/debug/perf_phaseA3_headless_tmux.sh stop
  5. View: cat ~/sahtd/data/perf/phaseA3_*/REPORT.md

Output: ~/sahtd/data/perf/phaseA3_YYYYMMDD_HHMMSS/
EOF
}

is_logging() {
    [ -f "$PID_FILE" ] && [ -f "$STATE_FILE" ]
}

get_run_dir() {
    [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || echo ""
}

# Source ROS environment
source_ros() {
    source /opt/ros/humble/setup.bash 2>/dev/null || true
    source "$SAHTD_ROOT/ros2/install/setup.bash" 2>/dev/null || true
}

# === Command: start ===

cmd_start() {
    local duration=0  # 0 = unlimited
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --duration) duration="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    
    print_header
    
    if is_logging; then
        echo -e "${YELLOW}Logging already in progress. Use 'stop' first.${NC}"
        exit 1
    fi
    
    # Create state directory
    mkdir -p "$STATE_DIR"
    
    # Create timestamped run directory
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local run_dir="$PERF_BASE_DIR/phaseA3_$timestamp"
    mkdir -p "$run_dir"
    echo "$run_dir" > "$STATE_FILE"
    
    echo -e "${GREEN}Run directory: $run_dir${NC}"
    echo ""
    
    # Save metadata
    {
        echo "# Phase A3 Performance Run"
        echo "timestamp: $timestamp"
        echo "host: $(hostname)"
        echo "git_branch: $(cd "$SAHTD_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
        echo "git_commit: $(cd "$SAHTD_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
        echo "duration: $duration"
        echo "mode: background_logger"
    } > "$run_dir/meta.yaml"
    
    # Source ROS
    source_ros
    
    echo -e "${YELLOW}Starting background loggers...${NC}"
    
    # Clear PID file
    > "$PID_FILE"
    
    # === Logger 1: GPU (nvidia-smi) ===
    if command -v nvidia-smi &>/dev/null; then
        nvidia-smi --query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu \
            --format=csv -l 1 > "$run_dir/gpu.csv" 2>&1 &
        echo $! >> "$PID_FILE"
        echo -e "  ${GREEN}✓${NC} GPU logger started (PID: $!)"
    else
        echo "nvidia-smi not available" > "$run_dir/gpu.csv"
        echo -e "  ${YELLOW}⚠${NC} GPU logger skipped (no nvidia-smi)"
    fi
    
    # === Logger 2: CPU (top) ===
    (while true; do
        top -b -n 1 | head -20
        echo "---"
        sleep 1
    done) > "$run_dir/cpu.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} CPU logger started (PID: $!)"
    
    # === Logger 3: ROS Topic Hz - Camera ===
    ros2 topic hz /camera/image_raw --window 1000 > "$run_dir/hz_camera.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Camera Hz logger started (PID: $!)"
    
    # === Logger 4: ROS Topic Hz - Detections ===
    ros2 topic hz /perception/detections --window 1000 > "$run_dir/hz_detections.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Detections Hz logger started (PID: $!)"
    
    # === Logger 5: ROS Topic Hz - Tracks ===
    ros2 topic hz /perception/tracks --window 1000 > "$run_dir/hz_tracks.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Tracks Hz logger started (PID: $!)"
    
    # === Logger 6: ROS Topic Hz - Cmd Body ===
    ros2 topic hz /sahtd/follow/cmd_body --window 1000 > "$run_dir/hz_cmd_body.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Cmd Body Hz logger started (PID: $!)"
    
    # === Logger 7: ROS Topic Bw - Camera ===
    ros2 topic bw /camera/image_raw --window 100 > "$run_dir/bw_camera.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Camera Bw logger started (PID: $!)"
    
    # === Logger 8: Events filter ===
    if [ -f "$EVENTS_LOG_FILE" ]; then
        tail -f "$EVENTS_LOG_FILE" 2>/dev/null | \
            grep --line-buffered -E 'TARGET_LOST|TARGET_REACQUIRED|GUARD_HOLD|FENCE' \
            > "$run_dir/events_filtered.log" 2>&1 &
        echo $! >> "$PID_FILE"
        echo -e "  ${GREEN}✓${NC} Events filter started (PID: $!)"
    fi
    
    # === Logger 9: Gazebo RTF (Real-Time Factor) ===
    # Echo the /world/<world>/stats topic for RTF data
    # The stats topic contains real_time_factor, sim_time, real_time
    (
        # Try to find the world name from topic list
        WORLD=$(gz topic -l 2>/dev/null | grep "/world/" | head -1 | sed 's|/world/\([^/]*\)/.*|\1|' || echo "default")
        echo "Detected world: $WORLD"
        gz topic -e -t "/world/$WORLD/stats" 2>&1 || echo "gz topic stats unavailable"
    ) > "$run_dir/gz_rtf.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Gazebo RTF logger started (PID: $!)"
    
    # === Logger 10: Process snapshot (1 Hz) ===
    # Identify what ruby, gz, px4, python are doing
    (while true; do
        echo "=== $(date '+%H:%M:%S') ==="
        ps aux --sort=-%cpu | grep -E "ruby|gz|px4|python|yolo|bytetrack" | grep -v grep | head -15
        echo ""
        sleep 2
    done) > "$run_dir/process_snapshot.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Process snapshot logger started (PID: $!)"
    
    # === Diagnostic: Headless verification ===
    echo ""
    echo -e "${CYAN}Headless Check:${NC}"
    if pgrep -f "gz sim -g" > /dev/null 2>&1; then
        echo -e "  ${RED}⚠ GUI mode detected${NC} (gz sim -g process found)"
        echo "headless: false" >> "$run_dir/meta.yaml"
    elif pgrep -f "gz sim" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Server-only mode (no -g flag found)"
        echo "headless: true" >> "$run_dir/meta.yaml"
    else
        echo -e "  ${YELLOW}?${NC} Gazebo not detected yet"
        echo "headless: unknown" >> "$run_dir/meta.yaml"
    fi
    
    # === Diagnostic: Ruby process identification ===
    echo ""
    echo -e "${CYAN}Ruby Process Check:${NC}"
    ruby_cmd=$(ps aux | grep ruby | grep -v grep | head -1)
    if [ -n "$ruby_cmd" ]; then
        echo -e "  ${YELLOW}Ruby found:${NC}"
        echo "  $ruby_cmd" | cut -c1-100
        echo "$ruby_cmd" > "$run_dir/ruby_process.txt"
    else
        echo -e "  ${GREEN}✓${NC} No ruby processes running"
        echo "No ruby processes" > "$run_dir/ruby_process.txt"
    fi
    
    # === Logger 11: Pipeline Latency Probe (per-message age logging) ===
    # Uses ROS_TIME (sim time) correctly
    echo ""
    echo -e "${CYAN}Starting latency probe...${NC}"
    python3 "$SCRIPT_DIR/perf_latency_probe.py" \
        --output-dir "$run_dir" > "$run_dir/latency_probe.log" 2>&1 &
    echo $! >> "$PID_FILE"
    echo -e "  ${GREEN}✓${NC} Latency probe started (PID: $!)"
    
    # === Logger 12: Per-process CPU/mem with pidstat ===
    echo ""
    echo -e "${CYAN}Starting per-process monitoring...${NC}"
    if command -v pidstat &>/dev/null; then
        # Collect PIDs of key processes
        GZ_SERVER_PID=$(pgrep -f "gz sim.*-r -s" | head -1)
        GZ_GUI_PID=$(pgrep -f "gz sim -g" | head -1)
        BRIDGE_PID=$(pgrep -f "image_bridge" | head -1)
        YOLO_PID=$(pgrep -f "yolo_node" | head -1)
        BYTETRACK_PID=$(pgrep -f "bytetrack" | head -1)
        FOLLOW_PID=$(pgrep -f "follow_node" | head -1)
        PX4_PID=$(pgrep -f "px4" | head -1)
        
        # Build PID list
        PIDS=""
        for p in $GZ_SERVER_PID $GZ_GUI_PID $BRIDGE_PID $YOLO_PID $BYTETRACK_PID $FOLLOW_PID $PX4_PID; do
            [ -n "$p" ] && PIDS="$PIDS -p $p"
        done
        
        if [ -n "$PIDS" ]; then
            # Log header
            echo "# PIDs: gz_server=$GZ_SERVER_PID gz_gui=$GZ_GUI_PID bridge=$BRIDGE_PID yolo=$YOLO_PID bytetrack=$BYTETRACK_PID follow=$FOLLOW_PID px4=$PX4_PID" > "$run_dir/pidstat.log"
            pidstat -u -r 1 $PIDS >> "$run_dir/pidstat.log" 2>&1 &
            echo $! >> "$PID_FILE"
            echo -e "  ${GREEN}✓${NC} pidstat logger started (PID: $!)"
        else
            echo -e "  ${YELLOW}⚠${NC} No target processes found for pidstat"
            echo "# No processes found" > "$run_dir/pidstat.log"
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} pidstat not available, using ps snapshots only"
        echo "# pidstat not installed" > "$run_dir/pidstat.log"
    fi
    
    # === Logger 13: System-level mpstat (all CPUs) ===
    if command -v mpstat &>/dev/null; then
        mpstat -P ALL 1 > "$run_dir/mpstat.log" 2>&1 &
        echo $! >> "$PID_FILE"
        echo -e "  ${GREEN}✓${NC} mpstat logger started (PID: $!)"
    else
        echo -e "  ${YELLOW}⚠${NC} mpstat not available"
        echo "# mpstat not installed" > "$run_dir/mpstat.log"
    fi
    
    # === Logger 14: iostat (if available) ===
    if command -v iostat &>/dev/null; then
        iostat -x 1 > "$run_dir/iostat.log" 2>&1 &
        echo $! >> "$PID_FILE"
        echo -e "  ${GREEN}✓${NC} iostat logger started (PID: $!)"
    else
        echo "# iostat not installed" > "$run_dir/iostat.log"
    fi
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           LOGGING STARTED                                ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Logs:${NC} $run_dir/"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  Status: ./scripts/debug/perf_phaseA3_headless_tmux.sh status"
    echo "  Stop:   ./scripts/debug/perf_phaseA3_headless_tmux.sh stop"
    echo ""
    
    # Auto-stop if duration specified
    if [ "$duration" -gt 0 ]; then
        echo -e "${YELLOW}Auto-stopping in ${duration} seconds...${NC}"
        (sleep "$duration" && "$0" stop) &
    fi
}

# === Command: stop ===

cmd_stop() {
    print_header
    
    if ! is_logging; then
        echo -e "${RED}No active logging session found.${NC}"
        return 1
    fi
    
    local run_dir
    run_dir=$(get_run_dir)
    
    echo -e "${YELLOW}Stopping loggers...${NC}"
    echo "Run directory: $run_dir"
    echo ""
    
    # Kill all logged PIDs
    if [ -f "$PID_FILE" ]; then
        while read -r pid; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                echo -e "  Stopped PID $pid"
            fi
        done < "$PID_FILE"
    fi
    
    # Also kill any orphaned ros2 topic processes
    pkill -f "ros2 topic hz" 2>/dev/null || true
    pkill -f "ros2 topic bw" 2>/dev/null || true
    
    sleep 1
    
    # Generate report
    echo ""
    echo -e "${YELLOW}Generating performance report...${NC}"
    if [ -f "$SCRIPT_DIR/perf_report_phaseA3.py" ]; then
        python3 "$SCRIPT_DIR/perf_report_phaseA3.py" --run-dir "$run_dir"
    else
        echo -e "${RED}Report generator not found${NC}"
    fi
    
    # Clean up state
    rm -rf "$STATE_DIR"
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           LOGGING COMPLETE                               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Results:${NC}"
    echo "  Logs:   $run_dir/"
    echo "  Report: $run_dir/REPORT.md"
    echo ""
    echo "View: cat $run_dir/REPORT.md"
    echo ""
}

# === Command: status ===

cmd_status() {
    print_header
    
    if is_logging; then
        local run_dir
        run_dir=$(get_run_dir)
        echo -e "  Status: ${GREEN}LOGGING${NC}"
        echo -e "  Run dir: $run_dir"
        echo ""
        echo -e "${CYAN}Active processes:${NC}"
        if [ -f "$PID_FILE" ]; then
            while read -r pid; do
                if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                    ps -p "$pid" -o pid,cmd --no-headers 2>/dev/null | head -c 80
                    echo ""
                fi
            done < "$PID_FILE"
        fi
        echo ""
        echo -e "${CYAN}Log sizes:${NC}"
        ls -lh "$run_dir"/*.log "$run_dir"/*.csv 2>/dev/null | awk '{print "  " $9 ": " $5}'
    else
        echo -e "  Status: ${RED}NOT LOGGING${NC}"
    fi
    echo ""
}

# === Main ===

if [[ $# -eq 0 ]]; then
    print_usage
    exit 0
fi

case $1 in
    start) shift; cmd_start "$@" ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    -h|--help) print_usage ;;
    *) echo -e "${RED}Unknown command: $1${NC}"; print_usage; exit 1 ;;
esac
