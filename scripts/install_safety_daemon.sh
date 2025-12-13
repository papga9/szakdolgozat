#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
SCRIPT_PATH="$REPO_DIR/scripts/safety_daemon.py"
SERVICE_NAME="safety-daemon"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/install_safety_daemon.sh" >&2
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Safety daemon not found at $SCRIPT_PATH" >&2
  exit 1
fi

# Create systemd unit (runs as root)
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=GPIO22 Shutdown Safety Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $SCRIPT_PATH
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
EOF

# Reload, enable, and start service
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo "Installation complete."
echo "Manage the service with:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl disable --now $SERVICE_NAME"
