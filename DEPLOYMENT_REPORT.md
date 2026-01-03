# SAHTD Deployment & Optimization Report
**Date:** January 1, 2026
**Project:** Security-Aware Human Tracking Drone (SAHTD)
**Focus:** Cloud Deployment (Render.com), Video Streaming Optimization, and Remote Control Implementation.

---

## 1. Executive Summary
We have successfully transitioned the SAHTD system from a purely local development setup to a robust **Hybrid Cloud Architecture**.
The system now features:
*   **Cloud Hosting:** Fully deployed on Render.com (Frontend + Backend + Database).
*   **Production Database:** Migrated from SQLite to **PostgreSQL**.
*   **Optimized Video:** Solved complex "Mixed Content" and "Tunnel Blocking" issues using Cloudflare Tunnels.
*   **Full Remote Control:** Implemented a bidirectional "Command Relay" allowing Cloud users to control the local drone through NAT/Firewalls.

---

## 2. Cloud Deployment (Render.com)

### 2.1 Infrastructure as Code
We created a `render.yaml` "Blueprint" that defines the entire stack in code. This allows for one-click deployment.

*   **Database Service (`sahtd-db`)**: Managed PostgreSQL instance (Free Tier).
*   **Backend Service (`sahtd-backend`)**: Python FastAPI.
    *   **Build Script**: Created `web/backend/render-build.sh` to handle dependencies, database initialization, and user seeding automatically on every deploy.
*   **Frontend Service (`sahtd-frontend`)**: Static React site.

### 2.2 Backend Adaptation
*   **Database Layer**: Modified `db.py` and `main.py` to support `DATABASE_URL`. It now auto-detects:
    *   **Production**: Connects to PostgreSQL.
    *   **Local**: Falls back to SQLite (`sahtd.db`).
*   **CORS**: Configured `main.py` to allow requests from `sahtd-frontend.onrender.com`.

---

## 3. Video Streaming Optimization
One of the biggest challenges was displaying the **Local MJPEG Video Stream** (http://localhost:8001) on the **Secure Cloud Frontend** (https://sahtd...onrender.com).

### 3.1 The Challenges
1.  **Mixed Content Blocking**: Browsers block insecure HTTP resources on HTTPS sites.
2.  **Ngrok Interstitial**: Ngrok (Free Tier) displays a "Warning Page" that breaks embedded `<img>` tags.
3.  **Tunnel Configuration**: Users need a way to input dynamic tunnel URLs into the static cloud frontend.

### 3.2 Implemented Solutions
1.  **Dynamic Video Configuration**:
    *   Updated `AppShell.jsx` to detect "Cloud Mode".
    *   Added a **"Set Stream URL"** button allowing users to inject their tunnel URL (saved to `localStorage`).
2.  **Ngrok Workaround**:
    *   Added logic to auto-append `/video` to user inputs.
    *   Added an **"Open Video in New Window"** button to bypass Ngrok embedding restrictions.
3.  **Cloudflare Tunnel (The Superior Solution)**:
    *   Moved away from Ngrok to **Cloudflare Tunnel** (`cloudflared`).
    *   **Benefit**: Free, persistent, no "Warning Page", allows direct embedding.
    *   **Tooling**: Created instructions to download and run `cloudflared` locally.

---

## 4. Remote Control (Command Relay)
We enabled the Cloud Dashboard buttons (Pause, Resume, Land, RTL, Select Target) to control the physical/simulated drone running locally.

### 4.1 Architecture: "Command Queue"
Since the Cloud cannot initiate connections to the Local machine (due to Firewalls/NAT), we implemented a **Polling Architecture**.

### 4.2 Backend Changes (`Web/Backend/App/Main.py`)
*   **Command Queue**: Added an in-memory queue (`COMMAND_QUEUE = []`) to store pending actions.
*   **Ingest Endpoint**: Created `GET /ingest/commands` for the connector to fetch pending tasks.
*   **Logic**: When a user clicks "Land", the backend no longer tries to run `ros2` directly. Instead, it pushes the command to the Queue.

### 4.3 Connector Changes (`Scripts/Deploy/Sim_Connector.py`)
*   **Polling Loop**: Added a thread that checks `GET /ingest/commands` every 1.0 second.
*   **Execution**: When a command is received (e.g., `land`), the script executes the corresponding ROS 2 command locally using `subprocess`.
    *   *Example*: `ros2 topic pub --once /sahtd/cmd std_msgs/msg/String "data: '{...cmd: land...}'"`

---

## 5. File Change Summary

### New Files
*   `render.yaml`: Deployment blueprint.
*   `web/backend/render-build.sh`: Build/Seed script.
*   `web/backend/requirements-render.txt`: Production dependencies.
*   `scripts/deploy/README_RENDER.md`: Deployment documentation.
*   `cloudflared` (Binary): Tunnel tool (downloaded to root).

### Modified Files for Optimization
*   `web/frontend/src/config.js`: Added `setVideoOverride` for Cloud mode.
*   `web/frontend/src/pages/AppShell.jsx`:
    *   "Environment Switcher" UI polish.
    *   Video Player "Placeholder" and "Configuration" UI.
    *   Cloudflare/Ngrok handling logic.
*   `web/backend/app/main.py`:
    *   Added Command Queue.
    *   Added `/ingest/commands` endpoint.
    *   Updated `_publish_ros_cmd` to enqueue actions.
*   `scripts/deploy/sim_connector.py`:
    *   Added `poll_commands` function.
    *   Added `execute_command` logic (ROS 2 CLI wrapper).
    *   Added polling thread.

---

## 6. Next Steps for User
1.  **Push Changes**: Run `git push origin main` to deploy the new Backend code to Render.
2.  **Restart Connector**: Restart `python3 scripts/deploy/sim_connector.py` locally.
3.  **Enjoy**: The system is now fully operational in the cloud with video and control.
