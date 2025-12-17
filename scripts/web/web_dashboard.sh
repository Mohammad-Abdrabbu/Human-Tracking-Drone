#!/usr/bin/env bash
# web_dashboard.sh - SAHTD Web Dashboard Launcher
# Unified script to start/stop frontend and backend services
#
# Usage:
#   web_dashboard.sh up [--backend-port <port>] [--frontend-port <port>]
#   web_dashboard.sh status
#   web_dashboard.sh logs [backend|frontend]
#   web_dashboard.sh reset

set -e

# === Colors ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# === Paths ===
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

BACKEND_DIR="$SAHTD_ROOT/web/backend"
FRONTEND_DIR="$SAHTD_ROOT/web/frontend"

# PID files for tracking processes
PID_DIR="$SAHTD_ROOT/.web_pids"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG_FILE="$PID_DIR/backend.log"
FRONTEND_LOG_FILE="$PID_DIR/frontend.log"

# Defaults
DEFAULT_BACKEND_PORT=8000
DEFAULT_FRONTEND_PORT=5173

# === Helper Functions ===

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  SAHTD Web Dashboard Launcher${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_ready() {
    local backend_port="$1"
    local frontend_port="$2"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              🚀 WEB DASHBOARD READY                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Access Points:${NC}"
    echo -e "  Frontend:  ${BOLD}http://localhost:${frontend_port}${NC}"
    echo -e "  Backend:   ${BOLD}http://localhost:${backend_port}${NC}"
    echo -e "  API Docs:  ${BOLD}http://localhost:${backend_port}/docs${NC}"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo -e "  View logs:    ${BOLD}./web_dashboard.sh logs backend${NC}"
    echo -e "  View logs:    ${BOLD}./web_dashboard.sh logs frontend${NC}"
    echo -e "  Check status: ${BOLD}./web_dashboard.sh status${NC}"
    echo -e "  Shutdown:     ${BOLD}./web_dashboard.sh reset${NC}"
    echo ""
}

print_usage() {
    cat << EOF
Usage:
  web_dashboard.sh up [--backend-port <port>] [--frontend-port <port>]
  web_dashboard.sh status
  web_dashboard.sh logs [backend|frontend]
  web_dashboard.sh reset

Subcommands:
  up        Start both backend and frontend servers
  status    Show current status of web services
  logs      View logs for backend or frontend
  reset     Stop all web services (safe shutdown)

Options for 'up':
  --backend-port <port>   Port for FastAPI backend (default: $DEFAULT_BACKEND_PORT)
  --frontend-port <port>  Port for Vite frontend (default: $DEFAULT_FRONTEND_PORT)

Examples:
  web_dashboard.sh up
  web_dashboard.sh up --frontend-port 3000
  web_dashboard.sh status
  web_dashboard.sh logs backend
  web_dashboard.sh reset
EOF
}

ensure_pid_dir() {
    mkdir -p "$PID_DIR"
}

is_process_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

get_process_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

wait_for_port() {
    local port="$1"
    local timeout="${2:-30}"
    local start_time=$(date +%s)
    
    while true; do
        if nc -z localhost "$port" 2>/dev/null; then
            return 0
        fi
        
        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -ge $timeout ]; then
            return 1
        fi
        sleep 0.5
    done
}

check_port_available() {
    local port="$1"
    if nc -z localhost "$port" 2>/dev/null; then
        return 1  # Port in use
    fi
    return 0  # Port available
}

stop_process() {
    local name="$1"
    local pid_file="$2"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -ne "  Stopping $name (PID: $pid)... "
            kill "$pid" 2>/dev/null || true
            # Wait up to 5 seconds for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    echo -e "${GREEN}✓${NC}"
                    rm -f "$pid_file"
                    return 0
                fi
                sleep 0.5
            done
            # Force kill if still running
            kill -9 "$pid" 2>/dev/null || true
            echo -e "${YELLOW}force killed${NC}"
            rm -f "$pid_file"
        else
            echo -e "  $name: ${YELLOW}not running${NC}"
            rm -f "$pid_file"
        fi
    else
        echo -e "  $name: ${YELLOW}not running${NC}"
    fi
}

# === Subcommand: up ===

cmd_up() {
    local backend_port=$DEFAULT_BACKEND_PORT
    local frontend_port=$DEFAULT_FRONTEND_PORT
    
    # Parse args
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backend-port) backend_port="$2"; shift 2 ;;
            --frontend-port) frontend_port="$2"; shift 2 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
    
    print_header
    ensure_pid_dir
    
    # Check if already running
    local backend_running=false
    local frontend_running=false
    
    if is_process_running "$BACKEND_PID_FILE"; then
        backend_running=true
    fi
    if is_process_running "$FRONTEND_PID_FILE"; then
        frontend_running=true
    fi
    
    if [ "$backend_running" = true ] && [ "$frontend_running" = true ]; then
        echo -e "${GREEN}✓ Web dashboard already running${NC}"
        echo ""
        cmd_status
        return 0
    fi
    
    # === Start Backend ===
    echo -e "${YELLOW}Starting Backend...${NC}"
    
    if [ "$backend_running" = true ]; then
        echo -e "  ${GREEN}✓ Backend already running${NC}"
    else
        # Check if port is available
        if ! check_port_available "$backend_port"; then
            echo -e "  ${RED}✗ Port $backend_port is already in use${NC}"
            echo -e "    Try: lsof -i :$backend_port"
            exit 1
        fi
        
        # Check for venv
        if [ ! -d "$BACKEND_DIR/.venv" ]; then
            echo -e "  ${RED}✗ Backend venv not found${NC}"
            echo -e "    Run: cd $BACKEND_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
            exit 1
        fi
        
        # Start backend
        echo -n "  Starting FastAPI on port $backend_port... "
        (
            cd "$BACKEND_DIR"
            source .venv/bin/activate
            uvicorn app.main:app --host 0.0.0.0 --port "$backend_port" >> "$BACKEND_LOG_FILE" 2>&1
        ) &
        local backend_pid=$!
        echo "$backend_pid" > "$BACKEND_PID_FILE"
        
        # Wait for backend to be ready
        if wait_for_port "$backend_port" 15; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ (timeout - check logs)${NC}"
        fi
    fi
    
    # === Start Frontend ===
    echo ""
    echo -e "${YELLOW}Starting Frontend...${NC}"
    
    if [ "$frontend_running" = true ]; then
        echo -e "  ${GREEN}✓ Frontend already running${NC}"
    else
        # Check if port is available
        if ! check_port_available "$frontend_port"; then
            echo -e "  ${YELLOW}⚠ Port $frontend_port in use, Vite will pick another${NC}"
        fi
        
        # Check for node_modules
        if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
            echo -e "  ${YELLOW}Installing dependencies...${NC}"
            (cd "$FRONTEND_DIR" && npm install) >> "$FRONTEND_LOG_FILE" 2>&1
        fi
        
        # Start frontend
        echo -n "  Starting Vite dev server on port $frontend_port... "
        (
            cd "$FRONTEND_DIR"
            npm run dev -- --host 0.0.0.0 --port "$frontend_port" >> "$FRONTEND_LOG_FILE" 2>&1
        ) &
        local frontend_pid=$!
        echo "$frontend_pid" > "$FRONTEND_PID_FILE"
        
        # Wait for frontend to be ready (may use different port if original is busy)
        sleep 2
        
        # Extract actual port from log
        local actual_port=$(grep -oP 'localhost:\K[0-9]+' "$FRONTEND_LOG_FILE" 2>/dev/null | tail -1 || echo "$frontend_port")
        
        if wait_for_port "$actual_port" 15; then
            echo -e "${GREEN}✓${NC}"
            frontend_port="$actual_port"
        else
            echo -e "${YELLOW}started (may take a moment)${NC}"
        fi
    fi
    
    # Final output
    print_ready "$backend_port" "$frontend_port"
}

# === Subcommand: status ===

cmd_status() {
    print_header
    ensure_pid_dir
    
    echo -e "${CYAN}Service Status:${NC}"
    echo ""
    
    # Backend status
    echo -n "  Backend:  "
    if is_process_running "$BACKEND_PID_FILE"; then
        local pid=$(get_process_pid "$BACKEND_PID_FILE")
        echo -e "${GREEN}RUNNING${NC} (PID: $pid)"
        
        # Check if responding
        echo -n "            "
        if curl -s "http://localhost:8000/health" > /dev/null 2>&1 || curl -s "http://localhost:8000/" > /dev/null 2>&1; then
            echo -e "API: ${GREEN}responding${NC}"
        else
            echo -e "API: ${YELLOW}not responding (may be starting)${NC}"
        fi
    else
        echo -e "${RED}NOT RUNNING${NC}"
    fi
    
    # Frontend status
    echo -n "  Frontend: "
    if is_process_running "$FRONTEND_PID_FILE"; then
        local pid=$(get_process_pid "$FRONTEND_PID_FILE")
        echo -e "${GREEN}RUNNING${NC} (PID: $pid)"
        
        # Try to find port from log
        if [ -f "$FRONTEND_LOG_FILE" ]; then
            local port=$(grep -oP 'localhost:\K[0-9]+' "$FRONTEND_LOG_FILE" 2>/dev/null | tail -1)
            if [ -n "$port" ]; then
                echo -e "            URL: ${BOLD}http://localhost:$port${NC}"
            fi
        fi
    else
        echo -e "${RED}NOT RUNNING${NC}"
    fi
    
    echo ""
    
    # Log file locations
    echo -e "${CYAN}Log Files:${NC}"
    echo "  Backend:  $BACKEND_LOG_FILE"
    echo "  Frontend: $FRONTEND_LOG_FILE"
    echo ""
}

# === Subcommand: logs ===

cmd_logs() {
    local service="${1:-}"
    
    case "$service" in
        backend)
            if [ -f "$BACKEND_LOG_FILE" ]; then
                echo -e "${CYAN}Backend Logs:${NC}"
                echo ""
                tail -f "$BACKEND_LOG_FILE"
            else
                echo -e "${YELLOW}No backend logs found${NC}"
            fi
            ;;
        frontend)
            if [ -f "$FRONTEND_LOG_FILE" ]; then
                echo -e "${CYAN}Frontend Logs:${NC}"
                echo ""
                tail -f "$FRONTEND_LOG_FILE"
            else
                echo -e "${YELLOW}No frontend logs found${NC}"
            fi
            ;;
        *)
            echo "Usage: web_dashboard.sh logs [backend|frontend]"
            exit 1
            ;;
    esac
}

# === Subcommand: reset ===

cmd_reset() {
    print_header
    ensure_pid_dir
    
    echo -e "${YELLOW}Shutting down web services...${NC}"
    echo ""
    
    # Stop frontend first (depends on backend)
    stop_process "Frontend" "$FRONTEND_PID_FILE"
    
    # Stop backend
    stop_process "Backend" "$BACKEND_PID_FILE"
    
    # Also try to kill any orphaned processes
    echo ""
    echo -e "${YELLOW}Cleaning up orphaned processes...${NC}"
    
    # Kill any uvicorn processes for our app
    pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  Killed orphaned uvicorn" || true
    
    # Kill any vite processes in our frontend dir
    pkill -f "vite.*sahtd.*frontend" 2>/dev/null && echo "  Killed orphaned vite" || true
    
    # Clean up log files (optional - keep them for debugging)
    # rm -f "$BACKEND_LOG_FILE" "$FRONTEND_LOG_FILE"
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✓ SHUTDOWN COMPLETE                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# === Main ===

if [[ $# -eq 0 ]]; then
    print_usage
    exit 0
fi

case $1 in
    up) shift; cmd_up "$@" ;;
    status) cmd_status ;;
    logs) shift; cmd_logs "$@" ;;
    reset) cmd_reset ;;
    -h|--help) print_usage ;;
    *) echo -e "${RED}Unknown command: $1${NC}"; print_usage; exit 1 ;;
esac
