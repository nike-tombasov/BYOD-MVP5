#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/systemd/byod-livekit.service" /etc/systemd/system/byod-livekit.service
install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/systemd/byod-backend.service" /etc/systemd/system/byod-backend.service
install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/byod-listener.conf" /etc/nginx/sites-available/byod-listener.conf
ln -sfn /etc/nginx/sites-available/byod-listener.conf /etc/nginx/sites-enabled/byod-listener.conf
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable byod-livekit byod-backend nginx
systemctl restart byod-livekit byod-backend nginx

systemctl --no-pager --full status byod-livekit | head -n 12 || true
systemctl --no-pager --full status byod-backend | head -n 12 || true

echo "Services enabled and started."
