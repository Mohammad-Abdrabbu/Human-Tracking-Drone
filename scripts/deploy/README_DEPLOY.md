# SAHTD Deployment Guide

## 🚀 Choose Your Path

### **Option A: Render.com (Recommended)**
**Status:** ✅ Fully Automated | Free Tier Available
Automatic deployment of Backend, Frontend, and PostgreSQL Database. No manual server configuration required.
👉 **[Read the Render Deployment Guide](README_RENDER.md)**

---

### **Option B: Manual VPS (Legacy)**
**Status:** 🛠️ Manual Setup Required (DigitalOcean, Linode, AWS EC2)
Full control over the server. Requires Nginx, Certbot, Systemd, and UFW configuration.
Follow the steps below for manual setup.

---

# SAHTD VPS Production Deployment (Manual)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION VPS                            │
│  (Always online, public internet, has domain)               │
│  Path: /home/sahtd/app/                                     │
│  - backend/          (FastAPI, uvicorn, port 8000)          │
│  - data/db/          (SQLite database)                      │
│  Frontend: /var/www/sahtd-frontend/ (static files)          │
│  Nginx (reverse proxy + TLS)                                │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ Tailscale (secure tunnel)
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
┌────────┴────────┐                  ┌──────┴────────┐
│   Server A      │                  │   Server B    │
│  (Main PC)      │                  │  (Laptop)     │
│ - Simulation    │                  │ - Simulation  │
│ - Connector     │                  │ - Connector   │
│   pushes data→  │                  │   pushes data→│
└─────────────────┘                  └───────────────┘
```

---

## Prerequisites

| Item | Value |
|------|-------|
| VPS OS | Ubuntu 22.04 LTS |
| Domain | YOUR_DOMAIN (replace everywhere) |
| GitHub | git@github.com:Mohammad-Abdrabbu/Human-Tracking-Drone.git |

---

## Phase 1: VPS System Setup

SSH as root:

```bash
# Create sahtd user
adduser --disabled-password --gecos "" sahtd
usermod -aG sudo sahtd
echo "sahtd ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/sahtd

# Install packages
apt update && apt install -y \
  nginx certbot python3-certbot-nginx \
  python3.10-venv python3-pip \
  nodejs npm ufw curl git

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# Configure firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# PROOF:
ufw status
tailscale status
```

---

## Phase 2: Deploy Backend (Lean)

As sahtd user:

```bash
su - sahtd

# Create app directory structure
mkdir -p ~/app/backend ~/app/data/db ~/app/data/logs

# Copy backend from local machine (run on LOCAL, not VPS)
# scp -r ~/sahtd/web/backend/* sahtd@VPS_IP:~/app/backend/

# OR clone and copy only web folder
git clone --depth 1 git@github.com:Mohammad-Abdrabbu/Human-Tracking-Drone.git /tmp/sahtd-temp
cp -r /tmp/sahtd-temp/web/backend/* ~/app/backend/
rm -rf /tmp/sahtd-temp

# Setup Python venv
cd ~/app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create secrets directory
sudo mkdir -p /etc/sahtd
sudo chown sahtd:sahtd /etc/sahtd

# Generate secrets and create env file
JWT_SECRET=$(openssl rand -hex 32)
INGEST_TOKEN=$(openssl rand -hex 32)

cat > /etc/sahtd/sahtd.env << EOF
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
INGEST_TOKEN=${INGEST_TOKEN}
TAILSCALE_ALLOWED_IPS=100.64.0.0/10
DATABASE_URL=sqlite:////home/sahtd/app/data/db/sahtd.db
SAHTD_ROOT=/home/sahtd/app
EOF

echo "========================================="
echo "SAVE THIS INGEST_TOKEN for sim connector:"
echo "${INGEST_TOKEN} 41ba16f14be6d4456d1ed6ab92749d460388d39d6683c3e98a8b8e4c0090c9bf" 
echo "========================================="

# Initialize database
cd ~/app/backend
source .venv/bin/activate
python -c "from app.db import init_db; init_db()"
```

---

## Phase 3: Backend Systemd Service

> **User**: `ramadan` (or any sudo user)  
> **Directory**: Any (paths are absolute)

```bash
# Exit sahtd user if logged in
exit

# Create systemd service (as ramadan with sudo)
sudo tee /etc/systemd/system/sahtd-backend.service << 'EOF'
[Unit]
Description=SAHTD Backend API
After=network.target

[Service]
Type=simple
User=sahtd
Group=sahtd
WorkingDirectory=/home/sahtd/app/backend
EnvironmentFile=/etc/sahtd/sahtd.env
ExecStart=/home/sahtd/app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sahtd-backend
sudo systemctl start sahtd-backend

# PROOF:
sudo systemctl status sahtd-backend
ss -lntp | grep 8000
curl http://127.0.0.1:8000/health
```

---

## Phase 4: Deploy Frontend

> **User**: `ramadan`  
> **Directory**: `~/sahtd/web/frontend` for build, then any for copy

```bash
# Build frontend
cd ~/sahtd/web/frontend
npm ci
npm run build

# Copy to nginx web root (from any directory)
sudo mkdir -p /var/www/sahtd-frontend
sudo cp -r ~/sahtd/web/frontend/dist/* /var/www/sahtd-frontend/
sudo chown -R www-data:www-data /var/www/sahtd-frontend

# PROOF:
ls -la /var/www/sahtd-frontend/
```

---

## Phase 5: Nginx + TLS

> **User**: `ramadan` (with sudo)  
> **Directory**: Any (paths are absolute)

### Step 5a: Create minimal nginx config for certbot

```bash
# Create initial nginx config (replace YOUR_DOMAIN)
sudo tee /etc/nginx/sites-available/sahtd << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN;
    root /var/www/sahtd-frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

# Enable site and remove default
sudo ln -sf /etc/nginx/sites-available/sahtd /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# PROOF:
sudo nginx -t
curl -I http://localhost/
```

### Step 5b: Get TLS certificate (requires real domain pointing to VPS)

```bash
# This only works if YOUR_DOMAIN DNS points to this server
sudo certbot --nginx -d YOUR_DOMAIN

# PROOF:
sudo certbot certificates
```

### Step 5c: Update nginx with full config (backend proxy + WebSocket)

```bash
# After certbot succeeds, replace with full config
# Copy content from scripts/deploy/nginx-sahtd.conf and:
# 1. Replace YOUR_DOMAIN with actual domain
# 2. Update SSL paths if certbot used different paths

sudo nano /etc/nginx/sites-available/sahtd
# (paste full config from nginx-sahtd.conf)

sudo nginx -t && sudo systemctl reload nginx

# PROOF:
curl -I https://YOUR_DOMAIN/
curl -I https://YOUR_DOMAIN/health
```

---

## Phase 6: Simulation Host Setup (Server A / Server B)

> **User**: `ramadan` (your normal user on simulation machine)  
> **Directory**: Start from home `~`

Run these on **each simulation machine** (Main PC = serverA, Laptop = serverB):

### Step 6a: Install Tailscale

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Verify connectivity to VPS
tailscale status
ping VPS_TAILSCALE_IP
```

### Step 6b: Create connector config

```bash
# Create config directory
mkdir -p ~/.config/sahtd

# Create env file (EDIT VALUES!)
cat > ~/.config/sahtd/connector.env << EOF
SAHTD_SOURCE_ID=serverA
SAHTD_VPS_URL=https://YOUR_DOMAIN
SAHTD_INGEST_TOKEN=PASTE_TOKEN_FROM_PHASE_2
SAHTD_ROOT=/home/ramadan/sahtd
EOF

# Install requests module
pip3 install requests
```

### Step 6c: Test connector manually

```bash
cd ~/sahtd
source ~/.config/sahtd/connector.env
python3 scripts/deploy/sim_connector.py

# Should see: [HEARTBEAT] 200: {"status":"ok"...}
# Press Ctrl+C to stop
```

### Step 6d: Install systemd user service

```bash
# Create user systemd directory
mkdir -p ~/.config/systemd/user

# Copy service file
cp ~/sahtd/scripts/deploy/sahtd-connector.service ~/.config/systemd/user/

# Enable and start
systemctl --user daemon-reload
systemctl --user enable sahtd-connector
loginctl enable-linger $USER

# Start service
systemctl --user start sahtd-connector

# PROOF:
systemctl --user status sahtd-connector
journalctl --user -u sahtd-connector -f
```

---

## Verification Commands

### On VPS (as ramadan with sudo)

```bash
# Backend running
sudo systemctl status sahtd-backend
ss -lntp | grep 8000

# Nginx running
sudo systemctl status nginx
sudo nginx -t

# Firewall
sudo ufw status

# TLS (replace YOUR_DOMAIN)
curl -I https://YOUR_DOMAIN/health

# Tailscale
tailscale status
```

### On Simulation Host (as ramadan)

```bash
# Tailscale connected
tailscale status

# Connector sending data
journalctl --user -u sahtd-connector -f

# Demo still works
cd ~/sahtd
./scripts/demo/demo_committee.sh up --guard on --markers on --events on --spawn --video on
```

---

## Troubleshooting

| Issue | User | Command |
|-------|------|---------|
| Backend not starting | ramadan | `journalctl -u sahtd-backend -f` |
| Nginx 502 error | ramadan | `ss -lntp \| grep 8000` |
| Ingest rejected | ramadan | Check token matches VPS INGEST_TOKEN |
| No data on website | ramadan | `journalctl --user -u sahtd-connector` |
| Permission denied | - | Make sure to use `sudo` for system paths |

