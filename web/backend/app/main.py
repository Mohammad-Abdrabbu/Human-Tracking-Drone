# app/main.py
import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt  # PyJWT
from dotenv import load_dotenv
import asyncio
import subprocess
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect, Header, Depends

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yaml

# Load .env variables at import time
load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-.env")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _get_sahtd_root() -> Path:
    """
    Get SAHTD repository root directory.
    
    Resolution order:
    1. SAHTD_ROOT environment variable
    2. Auto-detect by walking up from this file
    """
    # Check environment variable first
    env_root = os.getenv("SAHTD_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    
    # Auto-detect by walking up from this file
    current = Path(__file__).resolve().parent
    for _ in range(10):
        # Check for repo markers
        if (current / '.git').is_dir():
            return current
        if (current / 'ros2').is_dir() and (current / 'web').is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    # Fallback to ~/sahtd for backward compatibility
    return Path.home() / 'sahtd'


# Compute repo root once at module load
_SAHTD_ROOT = _get_sahtd_root()

# Events log file path (JSONL format)
EVENTS_LOG_PATH = Path(os.getenv(
    "EVENTS_LOG_PATH",
    str(_SAHTD_ROOT / "data" / "logs" / "events.jsonl")
))

# Telemetry log file path (JSONL format) - written by ROS telemetry_bridge_node
TELEMETRY_LOG_PATH = Path(os.getenv(
    "TELEMETRY_LOG_PATH",
    str(_SAHTD_ROOT / "data" / "logs" / "telemetry.jsonl")
))

# Fence YAML path (geo_guard.yaml from ROS)
FENCE_YAML_PATH = Path(os.getenv(
    "FENCE_YAML_PATH",
    str(_SAHTD_ROOT / "ros2" / "src" / "sahtd_launch" / "config" / "geo_guard.yaml")
))

# ---------------------------------------------------------------------------
# Password Hashing Utilities
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# In-Memory User Store (bcrypt hashed passwords)
# ---------------------------------------------------------------------------
# Pre-computed hashes for demo passwords:
#   operator: secret123
#   viewer: viewer123
# To generate new hashes: python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"

USERS_DB = {
    "operator@uop.edu.jo": {
        "password_hash": "$2b$12$yb/kNy/owvNXFcJQlsE.CeyY162xMBrRzSEgscfdTBsNKfRtomt8.",  # secret123
        "role": "operator",
    },
    "viewer@uop.edu.jo": {
        "password_hash": "$2b$12$xZlwf2.2qaaCxgvZzJV4bO5eFhlUF0EGFqxmfA6DcN217KzDmG1Bu",  # viewer123
        "role": "viewer",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class CommandRequest(BaseModel):
    source: str | None = "ui"



app = FastAPI(
    title="Security-Aware Human Tracking Drone Backend",
    version="0.4.0",
    description=(
        "Backend API for SAHTD GP2: login, live drone state, alerts, and basic controls."
    ),
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
# Automatically detect LAN IP for CORS origins.
# This allows the frontend to connect from any device on the same network.
# Override with CORS_LAN_IP environment variable if needed.
# ---------------------------------------------------------------------------

def _get_lan_ip() -> str:
    """Get the device's LAN IP address."""
    import socket
    try:
        # Create a socket to determine the outgoing IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # Connect to a public IP (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

_LAN_IP = os.getenv("CORS_LAN_IP", _get_lan_ip())

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    f"http://{_LAN_IP}:5173",  # Auto-detected LAN IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_access_token(subject: str, role: str) -> str:
    """Create a signed JWT for a given user/role."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

async def get_current_user(authorization: str = Header(...)) -> dict:
    """
    Simple Bearer token auth for REST endpoints.

    Expects: Authorization: Bearer <JWT>

    Returns decoded payload on success, raises 401 on failure.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def require_role(required_role: str):
    """
    Factory for role-checking dependency.
    Returns 403 Forbidden if user's role doesn't match required_role.
    
    Usage:
        @app.post("/cmd/pause")
        async def cmd_pause(user: dict = Depends(require_role("operator"))):
            ...
    """
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return user
    return role_checker


async def get_user_from_websocket(websocket: WebSocket) -> Optional[dict]:
    """
    Extract and verify JWT from the WebSocket query string, e.g.:

        ws://localhost:8000/ws/state?token=...JWT...

    Returns the decoded payload on success, or closes the socket and returns None on failure.
    """
    token = websocket.query_params.get("token")
    if not token:
        # Policy violation (no auth)
        await websocket.close(code=1008)
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        # Token expired
        await websocket.close(code=4001)
        return None
    except jwt.InvalidTokenError:
        # Invalid token
        await websocket.close(code=4002)
        return None


def iso_timestamp_z() -> str:
    """Return ISO-8601 timestamp with Z suffix and 3 decimal places (milliseconds)."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def append_event(event: dict) -> None:
    """
    Append an event to the events.jsonl log file.
    Creates the file and parent directories if they don't exist.
    """
    EVENTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


@app.get("/health", tags=["health"])
async def health_check():
    """
    Simple liveness check.

    Later we can include ROS/Drone status here.
    """
    return {"status": "ok"}


@app.get("/guard/fence", tags=["guard"])
async def get_fence():
    """
    Return fence polygon vertices from geo_guard.yaml.
    
    Response format:
    {
        "frame": "ENU",
        "vertices": [{"x": 0.0, "y": 0.0}, ...],
        "closed": true,
        "margin_m": 0.0
    }
    """
    if not FENCE_YAML_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fence YAML not found at {FENCE_YAML_PATH}",
        )
    
    try:
        with open(FENCE_YAML_PATH, "r") as f:
            config = yaml.safe_load(f)
        
        # Navigate to the geo_guard_node ros__parameters
        params = config.get("geo_guard_node", {}).get("ros__parameters", {})
        
        # Get vertices (flat array: x1, y1, x2, y2, ...)
        vertices_flat = params.get("vertices", [])
        if not vertices_flat or len(vertices_flat) % 2 != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid vertices in fence YAML (expected flat array with even length)",
            )
        
        # Convert to list of {x, y} objects
        vertices = []
        for i in range(0, len(vertices_flat), 2):
            vertices.append({
                "x": float(vertices_flat[i]),
                "y": float(vertices_flat[i + 1]),
            })
        
        return {
            "frame": "ENU",
            "vertices": vertices,
            "closed": True,
            "margin_m": float(params.get("soft_margin_m", 0.0)),
        }
        
    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse fence YAML: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading fence config: {e}",
        )


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest):
    """
    Authenticate user with email and password.

    - Accepts JSON: {"email": "...", "password": "..."}
    - Verifies password using bcrypt
    - On success: returns a JWT access token with role claim
    - Logs LOGIN_SUCCESS or LOGIN_FAIL to events.jsonl
    """
    user = USERS_DB.get(payload.email)
    now = iso_timestamp_z()
    
    if not user or not verify_password(payload.password, user["password_hash"]):
        # Log failed login attempt (do NOT log the password)
        append_event({
            "ts": now,
            "type": "LOGIN_FAIL",
            "message": f"Failed login attempt for {payload.email}",
            "source": "auth",
            "username": payload.email,
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Log successful login
    append_event({
        "ts": now,
        "type": "LOGIN_SUCCESS",
        "message": f"User {payload.email} logged in",
        "source": "auth",
        "username": payload.email,
        "role": user["role"],
    })

    access_token = create_access_token(subject=payload.email, role=user["role"])

    return TokenResponse(
        access_token=access_token,
        role=user["role"],
    )

@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket):
    """
    Live telemetry stream for the UI.

    Streams real telemetry from ~/sahtd/data/logs/telemetry.jsonl (tail -f style).
    If the file doesn't exist yet, sends periodic "waiting" messages.
    """
    await websocket.accept()

    user_payload = await get_user_from_websocket(websocket)
    if user_payload is None:
        # Socket already closed in helper
        return

    try:
        while True:
            # Check if telemetry.jsonl exists
            if not TELEMETRY_LOG_PATH.exists():
                # File doesn't exist yet, send waiting message
                msg = {
                    "type": "INFO",
                    "message": "Waiting for telemetry log...",
                    "ts": iso_timestamp_z(),
                }
                await websocket.send_json(msg)
                await asyncio.sleep(2.0)
                continue

            # Tail the telemetry.jsonl file
            with open(TELEMETRY_LOG_PATH, "r") as f:
                # Move to end of file
                f.seek(0, 2)
                
                while True:
                    line = f.readline()
                    if line:
                        try:
                            telemetry = json.loads(line.strip())
                            await websocket.send_json(telemetry)
                        except json.JSONDecodeError:
                            # Send raw line if parse fails
                            await websocket.send_text(line.strip())
                    else:
                        # No new data, wait a bit before checking again
                        await asyncio.sleep(0.3)
                        
                        # Check if file still exists (might have been rotated)
                        if not TELEMETRY_LOG_PATH.exists():
                            break

    except WebSocketDisconnect:
        # Client disconnected – nothing special to do for now
        pass
    except Exception as e:
        print(f"[WS /ws/state] Unhandled exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Alerts/events stream for the UI.

    Streams real events from ~/sahtd/data/logs/events.jsonl (tail -f style).
    If the file doesn't exist yet, sends periodic "waiting" messages.
    """
    await websocket.accept()

    user_payload = await get_user_from_websocket(websocket)
    if user_payload is None:
        return

    alert_id = 0

    try:
        while True:
            # Check if events.jsonl exists
            if not EVENTS_LOG_PATH.exists():
                # File doesn't exist yet, send waiting message
                alert_id += 1
                alert = {
                    "id": alert_id,
                    "type": "INFO",
                    "message": "Waiting for events log...",
                    "source": "backend",
                    "ts": iso_timestamp_z(),
                }
                await websocket.send_json(alert)
                await asyncio.sleep(3.0)
                continue

            # Tail the events.jsonl file
            with open(EVENTS_LOG_PATH, "r") as f:
                # Move to end of file
                f.seek(0, 2)
                
                while True:
                    line = f.readline()
                    if line:
                        try:
                            event = json.loads(line.strip())
                            alert_id += 1
                            # Ensure event has an id for frontend
                            event["id"] = alert_id
                            await websocket.send_json(event)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            pass
                    else:
                        # No new data, wait a bit before checking again
                        await asyncio.sleep(0.5)
                        
                        # Check if file still exists (might have been rotated)
                        if not EVENTS_LOG_PATH.exists():
                            break

    except WebSocketDisconnect:
        pass


def _publish_ros_cmd(cmd: str, user_email: str, req_id: str) -> bool:
    """
    Publish a command to /sahtd/cmd ROS topic via subprocess.
    Returns True if successful, False otherwise.
    """
    now = iso_timestamp_z()
    cmd_json = json.dumps({
        "req_id": req_id,
        "cmd": cmd,
        "user": user_email,
        "ts": now
    })
    
    # Use ros2 topic pub --once to publish single message
    # The JSON needs to be passed as the data field of std_msgs/String
    try:
        result = subprocess.run(
            [
                'ros2', 'topic', 'pub', '--once',
                '/sahtd/cmd', 'std_msgs/msg/String',
                f'data: \'{cmd_json}\''
            ],
            capture_output=True,
            text=True,
            timeout=5.0
        )
        if result.returncode != 0:
            print(f"[CMD] ros2 topic pub failed: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[CMD] ros2 topic pub timed out")
        return False
    except FileNotFoundError:
        print("[CMD] ros2 command not found (ROS2 not sourced?)")
        return False
    except Exception as e:
        print(f"[CMD] ros2 topic pub error: {e}")
        return False


def _command_response(cmd: str, user_email: str) -> dict:
    req_id = str(uuid.uuid4())
    now = iso_timestamp_z()
    
    # Log command request to events.jsonl
    event = {
        "ts": now,
        "type": "CMD_REQUEST",
        "message": f"Command '{cmd}' requested",
        "source": "web-ui",
        "user": user_email,
        "command": cmd,
        "req_id": req_id,
    }
    append_event(event)
    
    # Publish to ROS topic
    ros_success = _publish_ros_cmd(cmd, user_email, req_id)
    
    # Log to stdout for debugging
    status = "queued" if ros_success else "ros_failed"
    print(f"[CMD] {cmd} requested by {user_email} (req_id={req_id[:8]}...) -> {status}")
    
    return {
        "status": status,
        "command": cmd,
        "user": user_email,
        "req_id": req_id,
        "timestamp": now,
        "message": f"{cmd} command {'queued for execution' if ros_success else 'failed to queue (ROS unavailable)'}",
    }


@app.post("/cmd/pause", tags=["commands"])
async def cmd_pause(
    body: CommandRequest,
    user: dict = Depends(require_role("operator")),
):
    return _command_response("pause", user.get("sub", "unknown"))


@app.post("/cmd/resume", tags=["commands"])
async def cmd_resume(
    body: CommandRequest,
    user: dict = Depends(require_role("operator")),
):
    return _command_response("resume", user.get("sub", "unknown"))


@app.post("/cmd/rtl", tags=["commands"])
async def cmd_rtl(
    body: CommandRequest,
    user: dict = Depends(require_role("operator")),
):
    return _command_response("rtl", user.get("sub", "unknown"))


@app.post("/cmd/land", tags=["commands"])
async def cmd_land(
    body: CommandRequest,
    user: dict = Depends(require_role("operator")),
):
    return _command_response("land", user.get("sub", "unknown"))


class TargetSelectRequest(BaseModel):
    target_id: int


@app.post("/cmd/select", tags=["commands"])
async def cmd_select_target(
    body: TargetSelectRequest,
    user: dict = Depends(require_role("operator")),
):
    """Select a target to follow by ID."""
    target_id = body.target_id
    user_email = user.get("sub", "unknown")
    now = iso_timestamp_z()
    
    # Log event
    event = {
        "ts": now,
        "type": "TARGET_SELECT",
        "message": f"Target {target_id} selected",
        "source": "web-ui",
        "user": user_email,
        "target_id": target_id,
    }
    append_event(event)
    
    # Publish to ROS topic /perception/target_select (Int32)
    try:
        result = subprocess.run(
            [
                'ros2', 'topic', 'pub', '--once',
                '/perception/target_select', 'std_msgs/msg/Int32',
                f'data: {target_id}'
            ],
            capture_output=True,
            text=True,
            timeout=5.0
        )
        ros_success = result.returncode == 0
    except Exception as e:
        print(f"[SELECT] ros2 topic pub error: {e}")
        ros_success = False
    
    status = "selected" if ros_success else "ros_failed"
    print(f"[SELECT] Target {target_id} by {user_email} -> {status}")
    
    return {
        "status": status,
        "target_id": target_id,
        "user": user_email,
        "timestamp": now,
        "message": f"Target {target_id} {'selected' if ros_success else 'selection failed (ROS unavailable)'}",
    }


# Optional: allow `python -m app.main` as dev shortcut
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
