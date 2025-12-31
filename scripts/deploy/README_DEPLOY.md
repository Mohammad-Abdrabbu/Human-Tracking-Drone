# SAHTD VPS Production Deployment (Lean Approach)

Deploy only what's needed on VPS: `web/backend` + built frontend + database.

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
echo "${INGEST_TOKEN}"
echo "========================================="

# Initialize database
cd ~/app/backend
source .venv/bin/activate
python -c "from app.db import init_db; init_db()"
```

---

## Phase 3: Backend Systemd Service

```bash
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
```

---

## Phase 4: Deploy Frontend

```bash
# On LOCAL machine, build frontend
cd ~/sahtd/web/frontend
npm ci
npm run build

# Copy to VPS
scp -r dist/* sahtd@VPS_IP:/tmp/frontend-dist/

# On VPS:
sudo mkdir -p /var/www/sahtd-frontend
sudo cp -r /tmp/frontend-dist/* /var/www/sahtd-frontend/
sudo chown -R www-data:www-data /var/www/sahtd-frontend

# PROOF:
ls -la /var/www/sahtd-frontend/
```

---

## Phase 5: Nginx + TLS

```bash
# Create nginx config (replace YOUR_DOMAIN)
sudo tee /etc/nginx/sites-available/sahtd << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN;
    root /var/www/sahtd-frontend;
}
EOF

sudo ln -sf /etc/nginx/sites-available/sahtd /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Get TLS certificate
sudo certbot --nginx -d YOUR_DOMAIN

# Now expand nginx config (copy from nginx-sahtd.conf)
# After certbot, it will have SSL configured

# PROOF:
sudo nginx -t
curl -I https://YOUR_DOMAIN/
curl -I https://YOUR_DOMAIN/health
```

---

## Phase 6: Simulation Host Setup

Run on BOTH Server A and Server B:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Verify VPS connectivity
tailscale status
ping VPS_TAILSCALE_IP

# Create connector config
mkdir -p ~/.config/sahtd

cat > ~/.config/sahtd/connector.env << EOF
SAHTD_SOURCE_ID=serverA
SAHTD_VPS_URL=https://YOUR_DOMAIN
SAHTD_INGEST_TOKEN=PASTE_TOKEN_FROM_PHASE_2
SAHTD_ROOT=/home/ramadan/sahtd
EOF

# Install requests module
pip3 install requests

# Test connector manually
source ~/.config/sahtd/connector.env
python3 ~/sahtd/scripts/deploy/sim_connector.py

# Install systemd user service
mkdir -p ~/.config/systemd/user
cp ~/sahtd/scripts/deploy/sahtd-connector.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable sahtd-connector
loginctl enable-linger $USER

# Start when ready to push data
systemctl --user start sahtd-connector

# PROOF:
journalctl --user -u sahtd-connector -f
```

---

## Verification Commands

### VPS

```bash
# Backend running
sudo systemctl status sahtd-backend
ss -lntp | grep 8000

# Nginx running
sudo systemctl status nginx
sudo nginx -t

# Firewall
sudo ufw status

# TLS
curl -I https://YOUR_DOMAIN/health

# Tailscale
tailscale status
```

### Simulation Host

```bash
# Tailscale connected
tailscale status

# Connector sending data
journalctl --user -u sahtd-connector -f

# Demo still works
./scripts/demo/demo_committee.sh up --guard on --markers on --events on --spawn --video on
```

---

## Troubleshooting

| Issue | Command |
|-------|---------|
| Backend not starting | `journalctl -u sahtd-backend -f` |
| Nginx 502 error | Check backend: `ss -lntp \| grep 8000` |
| Ingest rejected | Check token matches VPS INGEST_TOKEN |
| No data on website | Check connector logs: `journalctl --user -u sahtd-connector` |
