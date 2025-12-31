# SAHTD VPS Deployment Guide

**ALL deployment files restored successfully.**

## Summary

Your main repository is **completely safe**. Only the deployment configuration files were deleted, and they have all been restored.

## What Was Restored

All files in `scripts/deploy/`:
- ✓ `sim_connector.py` - Connector script for simulation hosts
- ✓ `connector.env.example` - Connector environment template
- ✓ `sahtd-connector.service` - Systemd service for connector
- ✓ `sahtd-backend.service` - Systemd service for VPS backend
- ✓ `sahtd.env.example` - VPS environment template
- ✓ `nginx-sahtd.conf` - Nginx configuration

## Your Code Is Safe

All your important code is intact:
- ✓ `web/backend/` - Backend with ingest API
- ✓ `web/frontend/` - Frontend
- ✓ `ros2/` - ROS2 nodes
- ✓ `simulation/` - Gazebo simulation
- ✓ `data/` - Databases and logs

## Next Steps

The **backend code changes** (ingest API) are still in `web/backend/app/main.py` and ready to use.

When you have a VPS, follow the deployment guide by running commands from this README.
