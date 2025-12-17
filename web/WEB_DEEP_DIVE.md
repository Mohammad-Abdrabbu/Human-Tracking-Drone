# SAHTD Web Side Deep-Dive

> **Generated:** 2025-12-17 | **Updated:** 2025-12-17 (Day-2 upgrades)  
> **Scope:** Everything under `~/sahtd/web`

---

## 🚀 Quick Reference (Cheat Sheet)

### Run Commands

```bash
# Backend (FastAPI + Uvicorn)
cd ~/sahtd/web/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (Vite + React)
cd ~/sahtd/web/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Key Environment Variables

| Variable                    | Location                   | Default                |
|-----------------------------|----------------------------|------------------------|
| `JWT_SECRET`                | `backend/.env`             | `secret123`            |
| `JWT_ALGORITHM`             | `backend/.env`             | `HS256`                |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `backend/.env`             | `60`                   |
| `EVENTS_LOG_PATH`           | `backend/.env`             | `~/sahtd/data/logs/events.jsonl` |
| `VITE_API_BASE_URL`         | `frontend/.env.local`      | `http://127.0.0.1:8000` |
| `VITE_WS_BASE_URL`          | `frontend/.env.local`      | `ws://127.0.0.1:8000`   |

### LAN Demo Steps (Phone Access)

1. Find your LAN IP: `ip addr show | grep inet`
2. **Frontend:** Create `frontend/.env.local` (copy from `.env.local.example`):
   ```env
   VITE_API_BASE_URL=http://<LAN_IP>:8000
   VITE_WS_BASE_URL=ws://<LAN_IP>:8000
   ```
3. **Backend CORS:** Edit `backend/app/main.py` (see CORS section comments):
   ```python
   origins = [
       "http://localhost:5173",
       "http://127.0.0.1:5173",
       "http://<LAN_IP>:5173",  # Add your LAN IP
   ]
   ```
4. **Firewall (if UFW is enabled):**
   ```bash
   sudo ufw allow 8000/tcp
   sudo ufw allow 5173/tcp
   ```
5. **Restart servers** and access from phone: `http://<LAN_IP>:5173`

### Ports

| Service   | Port  | Protocol |
|-----------|-------|----------|
| Backend   | 8000  | HTTP/WS  |
| Frontend  | 5173  | HTTP     |

---

## 1. Directory Structure

```
sahtd/web/
├── backend/
│   ├── .env                 # Environment variables (JWT secrets)
│   ├── .venv/               # Python virtual environment
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py          # ⭐ FastAPI entrypoint
│   ├── requirements.txt     # Python dependencies
│   └── run_dev.sh           # Dev server startup script
│
└── frontend/
    ├── .gitignore
    ├── README.md
    ├── eslint.config.js
    ├── index.html           # HTML entrypoint
    ├── node_modules/        # Node dependencies
    ├── package.json         # ⭐ NPM config + scripts
    ├── package-lock.json
    ├── public/
    │   └── vite.svg
    ├── src/
    │   ├── App.jsx          # ⭐ Main routing component
    │   ├── App.css
    │   ├── auth.js          # Token storage utilities
    │   ├── index.css        # Global styles
    │   ├── main.jsx         # React entrypoint
    │   ├── assets/
    │   │   └── react.svg
    │   └── pages/
    │       ├── LoginPage.jsx    # Login form + API call
    │       └── AppShell.jsx     # ⭐ Main dashboard (WS, controls)
    └── vite.config.js       # Vite config
```

### Folder Summary

| Folder           | Purpose                                           | How to Run                          | Data Read/Write                                    | Dependencies                                         |
|------------------|---------------------------------------------------|-------------------------------------|---------------------------------------------------|------------------------------------------------------|
| **backend/**     | FastAPI REST API + WebSocket server               | `./run_dev.sh` or uvicorn directly  | Reads `.env`, serves mock data (future: ROS topics)| Python 3.10+, FastAPI, PyJWT, uvicorn, python-dotenv |
| **frontend/**    | Vite + React SPA for operator dashboard           | `npm run dev`                       | Reads from backend API/WS, writes to localStorage  | Node 18+, React 19, react-router-dom, Vite 7         |

---

## 2. Backend Deep Dive (FastAPI)

### 2.1 Entrypoint

**File:** [`backend/app/main.py`](file:///home/ramadan/sahtd/web/backend/app/main.py)

The FastAPI application is defined on line 45:

```python
app = FastAPI(
    title="Security-Aware Human Tracking Drone Backend",
    version="0.2.0",
    description="Backend API for SAHTD GP2: login, live drone state, alerts, and basic controls.",
)
```

### 2.2 All Routes/Endpoints

| Path           | Method | Purpose                         | Auth Required |
|----------------|--------|---------------------------------|---------------|
| `/health`      | GET    | Liveness check                  | ❌ No         |
| `/auth/login`  | POST   | User login, returns JWT         | ❌ No         |
| `/cmd/pause`   | POST   | Pause follow command            | ✅ Yes        |
| `/cmd/resume`  | POST   | Resume follow command           | ✅ Yes        |
| `/cmd/rtl`     | POST   | Return-to-launch command        | ✅ Yes        |
| `/cmd/land`    | POST   | Land now command                | ✅ Yes        |
| `/ws/state`    | WS     | Live state stream (1 Hz)        | ✅ Yes (query param) |
| `/ws/alerts`   | WS     | Alerts stream (every 5s)        | ✅ Yes (query param) |

### 2.3 WebSocket Endpoints

#### `/ws/state` (Lines 171-207)

**Purpose:** Streams live drone/follower state to the UI at 1 Hz.

**Authentication:** JWT token passed as query parameter:
```
ws://localhost:8000/ws/state?token=<JWT>
```

**Message Schema:**
```json
{
  "follow_state": "FOLLOWING",      // FOLLOWING | WAIT_LOCK | IDLE | etc.
  "guard_status": "NORMAL",         // NORMAL | GEOGUARD_HOLD | GEOGUARD_VIOLATION
  "stand_off_m": 3.0,               // Desired stand-off distance (meters)
  "fence_mode": "DRONE_KEEP_OUT",   // DRONE_KEEP_OUT | TARGET_KEEP_IN
  "operator": "operator@uop.edu.jo",
  "role": "operator",
  "seq": 42                         // Sequence counter
}
```

**Frequency:** 1 message per second

**Data Source:** Currently MOCK data. Future: ROS topics (`/sahtd/follow/state`, `/sahtd/geo_guard/status`)

---

#### `/ws/alerts` (Lines 217-270)

**Purpose:** Streams real events from `~/sahtd/data/logs/events.jsonl` (tail -f style).

**Authentication:** JWT token as query parameter.

**Behavior:**
- If `events.jsonl` doesn't exist yet, sends periodic "Waiting for events log..." messages (every 3s)
- Once file exists, tails it and streams each new JSONL line as a WebSocket message
- Handles file rotation gracefully

**Message Schema (from events.jsonl):**
```json
{
  "id": 1,
  "ts": "2025-12-17T15:22:26+00:00",
  "type": "CMD",                    // CMD | INFO | WARN | ERROR
  "message": "Command 'pause' executed",
  "source": "web-ui",
  "user": "operator@uop.edu.jo",
  "command": "pause"                // Only for CMD type
}
```

**Frequency:** Real-time (as events are appended to the log)

**Data Source:** `~/sahtd/data/logs/events.jsonl` (configurable via `EVENTS_LOG_PATH` env var)

---

### 2.4 Authentication Implementation

**Location:** [`backend/app/main.py`](file:///home/ramadan/sahtd/web/backend/app/main.py) lines 14-134

#### Login Route (Lines 147-169)

```python
@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest):
```

- **Input:** `{"email": "...", "password": "..."}`
- **Output:** `{"access_token": "...", "token_type": "bearer", "role": "operator"}`
- **Validation:** Checks against hardcoded `USERS_DB` dictionary

#### JWT/Session Logic

- **Token creation:** `create_access_token()` (lines 68-77)
- **Token validation (REST):** `get_current_user()` dependency (lines 79-106)
- **Token validation (WS):** `get_user_from_websocket()` (lines 109-133)

#### Hardcoded User Store (Lines 22-27)

```python
USERS_DB = {
    "operator@uop.edu.jo": {
        "password": "secret123",  # plain text for now
        "role": "operator",
    }
}
```

> ⚠️ **Security Note:** Passwords are stored in plain text. For production, use bcrypt/argon2 hashing.

#### Secrets/Config Location

**File:** [`backend/.env`](file:///home/ramadan/sahtd/web/backend/.env)

```env
JWT_SECRET=secret123
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

### 2.5 CORS Configuration

**Location:** [`backend/app/main.py`](file:///home/ramadan/sahtd/web/backend/app/main.py) lines 53-65

```python
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
```

#### To Enable LAN Demo

Edit lines 54-57 to add your LAN IP:

```python
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.1.100:5173",  # <-- Add your LAN IP here
]
```

---

### 2.6 Command Handling

**Location:** Lines 242-284

#### Code Path: HTTP Route → Action

```
┌─────────────────────┐
│ POST /cmd/pause     │
│ (or resume/rtl/land)│
└──────────┬──────────┘
           │ Authorization header validated
           ▼
┌─────────────────────┐
│ get_current_user()  │  ← JWT decoded, user extracted
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ cmd_pause()         │  ← Route handler
│ cmd_resume()        │
│ cmd_rtl()           │
│ cmd_land()          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ _command_response() │  ← Logs command, returns ack
└─────────────────────┘
           │
           ▼ (FUTURE)
┌─────────────────────┐
│ ROS publisher       │  ← /sahtd/cmd topic
│ or MAVSDK call      │  ← MAVLink command
└─────────────────────┘
```

**Current Implementation (Lines 275-297):**

```python
def _command_response(cmd: str, user_email: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    
    # Log command to events.jsonl
    event = {
        "ts": now,
        "type": "CMD",
        "message": f"Command '{cmd}' executed",
        "source": "web-ui",
        "user": user_email,
        "command": cmd,
    }
    append_event(event)
    
    print(f"[CMD] {cmd} requested by {user_email} at {now}")
    return { ... }
```

**What happens when a command is issued:**
1. Event is appended to `~/sahtd/data/logs/events.jsonl`
2. `/ws/alerts` clients receive the event in real-time
3. HTTP response is returned to the caller

> ⚠️ **Note:** ROS/MAVSDK integration is still TODO. Commands are logged but not yet sent to the drone.

---

## 3. Frontend Deep Dive (Vite + React)

### 3.1 Framework & Stack

| Component        | Technology         | Version |
|------------------|--------------------|---------|
| Build tool       | Vite               | 7.2.4   |
| Framework        | React              | 19.2.0  |
| Routing          | react-router-dom   | 7.9.6   |
| State management | React useState     | -       |
| Styling          | Vanilla CSS        | -       |

### 3.2 Entrypoint

**File:** [`frontend/src/main.jsx`](file:///home/ramadan/sahtd/web/frontend/src/main.jsx)

```jsx
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

### 3.3 Routing/Pages

**File:** [`frontend/src/App.jsx`](file:///home/ramadan/sahtd/web/frontend/src/App.jsx)

| Route      | Component      | Description                    | Auth Required |
|------------|----------------|--------------------------------|---------------|
| `/login`   | `LoginPage`    | Login form                     | ❌ No         |
| `/app`     | `AppShell`     | Main dashboard                 | ✅ Yes        |
| `*`        | Redirect       | Redirects to `/login`          | -             |

**Auth Guard (Lines 7-12):**

```jsx
function RequireAuth({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
```

### 3.4 Main UI Components

| Component       | File                        | Purpose                                |
|-----------------|-----------------------------|----------------------------------------|
| `LoginPage`     | `pages/LoginPage.jsx`       | Email/password form, login API call    |
| `AppShell`      | `pages/AppShell.jsx`        | Dashboard: state, alerts, controls     |

### 3.5 All API Calls

| File/Function                  | Endpoint          | Method | Request Body                        |
|--------------------------------|-------------------|--------|-------------------------------------|
| `LoginPage.jsx` → `handleSubmit` | `/auth/login`    | POST   | `{"email": "...", "password": "..."}` |
| `AppShell.jsx` → `handleCommand` | `/cmd/{pause\|resume\|rtl\|land}` | POST | `{"source": "ui"}` |

#### Login API Call (LoginPage.jsx, lines 28-55)

```javascript
const response = await fetch(`${API_BASE_URL}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
});
```

#### Command API Call (AppShell.jsx, lines 119-152)

```javascript
const response = await fetch(`${API_BASE_URL}/cmd/${cmd}`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ source: 'ui' }),
});
```

### 3.6 WebSocket Client Logic

**File:** [`frontend/src/pages/AppShell.jsx`](file:///home/ramadan/sahtd/web/frontend/src/pages/AppShell.jsx)

#### Connection Setup

**State WebSocket (Lines 20-57):**

```javascript
const url = `${WS_BASE_URL}/ws/state?token=${encodeURIComponent(token)}`;
const ws = new WebSocket(url);

ws.onopen = () => setConnectionStatus('connected');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setStateMsg(data);
};
ws.onerror = () => setConnectionStatus('error');
ws.onclose = () => setConnectionStatus('disconnected');
```

**Alerts WebSocket (Lines 60-98):**

Similar pattern, maintains list of last 50 alerts.

#### Reconnection Logic

> ⚠️ **Current State:** No automatic reconnection. If connection drops, status shows "disconnected" but no retry logic exists.

**Recommendation:** Add exponential backoff reconnection:

```javascript
// TODO: Implement reconnection with exponential backoff
```

### 3.7 API Base URL Configuration

**Current Implementation (Environment-based):**

**In `LoginPage.jsx` (line 6):**
```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
```

**In `AppShell.jsx` (lines 6-7):**
```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000';
```

#### Configuration for LAN Demo

**Step 1: Create `frontend/.env.local`** (copy from `.env.local.example`):

```env
# frontend/.env.local
VITE_API_BASE_URL=http://192.168.1.100:8000
VITE_WS_BASE_URL=ws://192.168.1.100:8000
```

**Step 2: Restart Vite dev server**

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

> 💡 **Note:** `.env.local` is gitignored by default. Do not commit secrets.

---

## 4. How to Run Locally + On LAN (Phone Demo)

### 4.1 Backend Setup

```bash
# Navigate to backend
cd ~/sahtd/web/backend

# Create venv (if not exists)
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with LAN access
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.2 Frontend Setup

```bash
# Navigate to frontend
cd ~/sahtd/web/frontend

# Install dependencies
npm install

# Run with LAN access
npm run dev -- --host 0.0.0.0 --port 5173
```

### 4.3 Firewall Steps (If UFW Enabled)

```bash
# Check UFW status
sudo ufw status

# Allow backend port
sudo ufw allow 8000/tcp

# Allow frontend port
sudo ufw allow 5173/tcp

# Verify
sudo ufw status
```

### 4.4 Health Check Checklist

| Check | Command/Action | Expected Result |
|-------|----------------|-----------------|
| ✅ Backend health | `curl http://localhost:8000/health` | `{"status":"ok"}` |
| ✅ Backend from LAN | `curl http://<LAN_IP>:8000/health` | `{"status":"ok"}` |
| ✅ Frontend local | Open `http://localhost:5173` | Login page renders |
| ✅ Frontend from phone | Open `http://<LAN_IP>:5173` | Login page renders |
| ✅ Login works | Enter credentials, click Login | Redirects to `/app` |
| ✅ State WS connected | Check "State WS: connected" in UI | Shows "connected" |
| ✅ Alerts WS connected | Check "Alerts WS: connected" in UI | Shows "connected" |
| ✅ Command works | Click Pause button | Status shows "Command accepted" |

---

## 5. Live Demo "What to Show"

### 5.1 Feature Checklist

| Feature | Location in UI | Data Source | Status |
|---------|----------------|-------------|--------|
| **Login** | `/login` page | Hardcoded user DB | ✅ Working |
| **Live State** | Main pill (FOLLOWING/NORMAL) | Mock WS `/ws/state` | ✅ Working (mock) |
| **Stand-off distance** | State metadata | Mock WS | ✅ Working (mock 3.0m) |
| **Fence mode** | State metadata | Mock WS | ✅ Working (mock) |
| **WS Connection status** | State WS / Alerts WS labels | React state | ✅ Working |
| **Alerts feed** | Alerts section (scrollable) | Mock WS `/ws/alerts` | ✅ Working (mock) |
| **Guard status** | Pill color (green/yellow/red) | Mock WS | ✅ Working (mock) |
| **Pause command** | Controls → Pause button | `/cmd/pause` | ✅ Working (logs only) |
| **Resume command** | Controls → Resume button | `/cmd/resume` | ✅ Working (logs only) |
| **RTL command** | Controls → RTL button | `/cmd/rtl` | ✅ Working (logs only) |
| **Land command** | Controls → Land button | `/cmd/land` | ✅ Working (logs only) |
| **Logout** | Header → Logout button | Clears localStorage | ✅ Working |

### 5.2 Missing Pieces / TODO Items

| Item | Current State | Impact | Priority |
|------|---------------|--------|----------|
| **ROS integration** | No ROS bridge | No real drone data | 🔴 High |
| **Video streaming** | Not implemented | No camera feed | 🔴 High |
| **Selected target ID** | Not displayed | Missing from UI | 🟡 Medium |
| **Events log** | Only alerts, no event history | Limited audit trail | 🟡 Medium |
| **WS reconnection** | No auto-reconnect | Poor reliability | 🟡 Medium |
| **Debug panel** | Not implemented | Limited diagnostics | 🟢 Low |
| **Environment config** | Hardcoded URLs | Manual edits needed | 🟢 Low |

### 5.3 Risks / Performance Notes

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Heavy CPU** | N/A for mock data. Real ROS bridge + video could be heavy. | Use efficient image compression (MJPEG/H.264) |
| **Video streaming** | Not implemented. Will require separate solution (ros2web_video, gstreamer, etc.) | Plan WebRTC or MJPEG endpoint |
| **Token expiry** | 60-minute tokens, no refresh logic | User must re-login after expiry |
| **Plain text passwords** | Security risk if DB is exposed | Hash passwords before production |
| **No HTTPS** | Tokens sent in clear text on LAN | Use nginx + SSL for production |

---

## 6. Appendix

### Files Scanned

```
backend/.env
backend/app/__init__.py
backend/app/main.py
backend/requirements.txt
backend/run_dev.sh
frontend/.gitignore
frontend/README.md
frontend/eslint.config.js
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/public/vite.svg
frontend/src/App.css
frontend/src/App.jsx
frontend/src/assets/react.svg
frontend/src/auth.js
frontend/src/index.css
frontend/src/main.jsx
frontend/src/pages/AppShell.jsx
frontend/src/pages/LoginPage.jsx
frontend/vite.config.js
```

### Most Important Files

1. **`backend/app/main.py`** - FastAPI server, all routes, WebSocket endpoints, auth
2. **`frontend/src/pages/AppShell.jsx`** - Main dashboard, WS client, command buttons
3. **`frontend/src/pages/LoginPage.jsx`** - Login form, auth API call
4. **`frontend/src/auth.js`** - Token storage utilities
5. **`backend/.env`** - JWT secrets and config

### One-Liner Summary

> **SAHTD Web Stack:** Vite+React SPA (port 5173) → FastAPI backend (port 8000) with JWT auth, WebSocket state/alerts streams (1Hz mock data), and REST command endpoints for pause/resume/rtl/land – currently mock implementation pending ROS integration.
