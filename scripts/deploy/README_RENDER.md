# SAHTD Render Deployment Guide (Recommended)

This guide explains how to deploy the SAHTD system using [Render](https://render.com), a fully managed Platform as a Service (PaaS).

**Status:** ✅ Fully Supported (Backend, Frontend, PostgreSQL, Auto-Deploy)

---

## 🚀 Quick Start (5 Minutes)

### 1. Prerequisites
- A GitHub account with the `Human-Tracking-Drone` repository forked/pushed.
- A [Render.com](https://render.com) account (Free tier works).

### 2. Deployment Steps

1.  **Log in to Render Dashboard**.
2.  Click **New +** → **Blueprint**.
3.  Connect your GitHub repository.
4.  Render will automatically detect `render.yaml`.
5.  Click **Apply**.

Render will create three services automatically:
- **sahtd-db**: PostgreSQL Database (Free).
- **sahtd-backend**: Python FastAPI Web Service (Free).
- **sahtd-frontend**: Static Site (Free).

### 3. Verification

Once deployment finishes (green checkmarks):
- **Frontend URL:** `https://sahtd-frontend.onrender.com`
- **Backend URL:** `https://sahtd-backend.onrender.com`

Visit the Frontend URL and login with default credentials:
- **Email:** `operator@uop.edu.jo`
- **Password:** `operator123`

*(Note: The database is automatically seeded with users during the first deploy.)*

---

## 🔌 Connecting Simulation Host (Connector)

To stream drone data to your cloud deployment, configure the local connector on your simulation machine.

### 1. Get Ingest Token
Go to **Render Dashboard** → **sahtd-backend** → **Environment** and copy the value of `INGEST_TOKEN`.

### 2. Configure Connector (Local Machine)

Run this terminal command (replace `YOUR_TOKEN`):

```bash
mkdir -p ~/.config/sahtd && cat > ~/.config/sahtd/connector.env << EOF
# SAHTD Simulation Connector - Render Production
export SAHTD_SOURCE_ID=serverA
export SAHTD_VPS_URL=https://sahtd-backend.onrender.com
export SAHTD_INGEST_TOKEN=YOUR_TOKEN_HERE
export SAHTD_ROOT=$HOME/sahtd
EOF
```

### 3. Run Connector

```bash
cd ~/sahtd
source ~/.config/sahtd/connector.env
python3 scripts/deploy/sim_connector.py
```

You should see: `[HEARTBEAT] 200: {"status":"ok"...}`

---

## 🛠️ Configuration Details

### Database (PostgreSQL)
The system automatically switches to PostgreSQL when `DATABASE_URL` is detected.
- **Local Dev:** SQLite (`data/db/sahtd.db`)
- **Render:** PostgreSQL (Managed)

### Auto-Seeding
The `render.yaml` blueprint uses a custom build script (`web/backend/render-build.sh`) which:
1. Installs dependencies.
2. Initializes database tables (`init_db`).
3. Seeds default users (`seed_db.py`).

### Frontend Configuration
The frontend uses `.env.production` to point to the Render backend URL:
```ini
VITE_API_BASE_URL=https://sahtd-backend.onrender.com
VITE_WS_BASE_URL=wss://sahtd-backend.onrender.com
```

### CORS
The backend automatically allows requests from `https://sahtd-frontend.onrender.com`.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Login Fails (401)** | Database might be empty. Check build logs for "Seeding users..." or trigger manual deploy. |
| **CORS Error** | Ensure frontend URL is in `CORS_ORIGINS` in backend environment or `main.py`. |
| **Ingest 403** | Check `INGEST_TOKEN` matches between `connector.env` and Render Environment. |
| **Frontend 404** | Hard refresh (Ctrl+Shift+R) to clear old cache. |
