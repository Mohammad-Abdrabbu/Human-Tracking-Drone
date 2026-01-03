#!/bin/bash
# install_services.sh
# Installs fitexpo services to system level

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

SAHTD_ROOT=${SAHTD_ROOT:-/home/ramadan/sahtd}
SERVICE_DIR="/etc/systemd/system"

cp $SAHTD_ROOT/systemd/fitexpo-px4.service $SERVICE_DIR/
cp $SAHTD_ROOT/systemd/fitexpo-ros.service $SERVICE_DIR/
cp $SAHTD_ROOT/systemd/fitexpo-orchestrator.service $SERVICE_DIR/
cp $SAHTD_ROOT/systemd/fitexpo.target $SERVICE_DIR/

systemctl daemon-reload

echo "Services installed to $SERVICE_DIR"
