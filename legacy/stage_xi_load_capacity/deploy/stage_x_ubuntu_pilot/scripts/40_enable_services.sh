#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}FATAL: Service enable/start failed.${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
NGINX_CONF_SRC="$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/nginx.conf"
NGINX_CONF_DST="/etc/nginx/nginx.conf"
NGINX_BACKUP=""

install_nginx_main_config() {
  if [[ -f "$NGINX_CONF_DST" ]]; then
    NGINX_BACKUP="${NGINX_CONF_DST}.byod-backup.$(date -u +%Y%m%dT%H%M%SZ)"
    cp -a "$NGINX_CONF_DST" "$NGINX_BACKUP"
  fi

  install -m 0644 "$NGINX_CONF_SRC" "$NGINX_CONF_DST"
  if ! nginx -t; then
    if [[ -n "$NGINX_BACKUP" && -f "$NGINX_BACKUP" ]]; then
      cp -a "$NGINX_BACKUP" "$NGINX_CONF_DST"
      nginx -t || true
    fi
    printf "%b\n" "${RED}ERROR: New nginx.conf failed validation; restored previous config if a backup existed.${NC}" >&2
    exit 1
  fi
}

install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/systemd/byod-livekit.service" /etc/systemd/system/byod-livekit.service
install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/systemd/byod-backend.service" /etc/systemd/system/byod-backend.service
install -d -m 0755 /etc/systemd/system/nginx.service.d
install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/systemd/nginx.service.d/override.conf" /etc/systemd/system/nginx.service.d/override.conf

install_nginx_main_config
install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/byod-listener.conf" /etc/nginx/sites-available/byod-listener.conf
ln -sfn /etc/nginx/sites-available/byod-listener.conf /etc/nginx/sites-enabled/byod-listener.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t

systemctl daemon-reload
systemctl enable byod-livekit byod-backend nginx
systemctl restart byod-livekit byod-backend nginx

systemctl --no-pager --full status byod-livekit | head -n 12 || true
systemctl --no-pager --full status byod-backend | head -n 12 || true
systemctl --no-pager --full status nginx | head -n 12 || true

printf "%b\n" "${CYAN}SUCCESS: Services enabled and started.${NC}"
