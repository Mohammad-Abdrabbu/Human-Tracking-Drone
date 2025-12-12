# app/main.py
import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from dotenv import load_dotenv
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect, Header, Depends

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env variables at import time
load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-.env")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Hardcoded user store for now (we can move to DB later)
USERS_DB = {
    "operator@uop.edu.jo": {
        "password": "secret123",  # plain text for now
        "role": "operator",
    }
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
    version="0.2.0",
    description=(
        "Backend API for SAHTD GP2: login, live drone state, alerts, and basic controls."
    ),
)

# CORS so Vite/React can call the API from localhost:5173
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
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



@app.get("/health", tags=["health"])
async def health_check():
    """
    Simple liveness check.

    Later we can include ROS/Drone status here.
    """
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest):
    """
    Basic login:

    - Accepts JSON: {"email": "...", "password": "..."}
    - Checks against hardcoded operator user
    - On success: returns a JWT access token + role
    """
    user = USERS_DB.get(payload.email)
    if not user or payload.password != user["password"]:
        # invalid email or password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(subject=payload.email, role=user["role"])

    return TokenResponse(
        access_token=access_token,
        role=user["role"],
    )

@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket):
    """
    Live state stream for the UI.

    For now: mock data every 1 second.
    Later: plug real ROS / follow / geo-guard status.
    """
    await websocket.accept()

    user_payload = await get_user_from_websocket(websocket)
    if user_payload is None:
        # Socket already closed in helper
        return

    email = user_payload.get("sub", "unknown")
    role = user_payload.get("role", "unknown")

    try:
        counter = 0
        while True:
            # Mock state (you can tweak these fields anytime)
            message = {
                "follow_state": "FOLLOWING",       # or WAIT_LOCK, IDLE, etc.
                "guard_status": "NORMAL",          # or GEOGUARD_HOLD, GEOGUARD_VIOLATION
                "stand_off_m": 3.0,               # desired stand-off distance
                "fence_mode": "DRONE_KEEP_OUT",   # or TARGET_KEEP_IN later
                "operator": email,
                "role": role,
                "seq": counter,
            }
            await websocket.send_json(message)
            counter += 1
            await asyncio.sleep(1.0)  # 1 Hz for state
    except WebSocketDisconnect:
        # Client disconnected – nothing special to do for now
        pass


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Alerts stream for the UI.

    For now: send fake alerts every 5 seconds.
    Later: publish real geo-guard / failsafe / operator alerts.
    """
    await websocket.accept()

    user_payload = await get_user_from_websocket(websocket)
    if user_payload is None:
        return

    email = user_payload.get("sub", "unknown")

    try:
        alert_id = 1
        while True:
            alert = {
                "id": alert_id,
                "type": "INFO",  # e.g. INFO/WARN/ERROR
                "message": f"Mock alert #{alert_id} for {email}",
                "source": "backend-mock",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_json(alert)
            alert_id += 1
            await asyncio.sleep(5.0)  # one alert every 5 seconds
    except WebSocketDisconnect:
        pass

def _command_response(cmd: str, user_email: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    # For now we just log; later these will publish to ROS / MAVSDK.
    print(f"[CMD] {cmd} requested by {user_email} at {now}")
    return {
        "status": "ok",
        "command": cmd,
        "user": user_email,
        "timestamp": now,
        "message": f"{cmd} command accepted",
    }


@app.post("/cmd/pause", tags=["commands"])
async def cmd_pause(
    body: CommandRequest,
    user: dict = Depends(get_current_user),
):
    return _command_response("pause", user.get("sub", "unknown"))


@app.post("/cmd/resume", tags=["commands"])
async def cmd_resume(
    body: CommandRequest,
    user: dict = Depends(get_current_user),
):
    return _command_response("resume", user.get("sub", "unknown"))


@app.post("/cmd/rtl", tags=["commands"])
async def cmd_rtl(
    body: CommandRequest,
    user: dict = Depends(get_current_user),
):
    return _command_response("rtl", user.get("sub", "unknown"))


@app.post("/cmd/land", tags=["commands"])
async def cmd_land(
    body: CommandRequest,
    user: dict = Depends(get_current_user),
):
    return _command_response("land", user.get("sub", "unknown"))


# Optional: allow `python -m app.main` as dev shortcut
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
