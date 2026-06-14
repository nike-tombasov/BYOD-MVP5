#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

(
  cd /opt/byod/app
  runuser -u byod -- /opt/byod/app/.venv/bin/python -c 'import backend.main'
)
echo "backend_import_ok"

nginx -t
systemctl --no-pager --full status byod-livekit
systemctl --no-pager --full status byod-backend
systemctl --no-pager --full status nginx

runuser -u www-data -- test -r /opt/byod/listener/index.html
echo "listener_readable_by_nginx_ok"

curl -sf http://127.0.0.1/ >/dev/null
echo "listener_through_nginx_ok"
curl -sf http://127.0.0.1/health >/dev/null
echo "backend_health_through_nginx_ok"

ss -tulpen | awk '/7880|7881|8000|:80 / {print}'

cat <<'EOF'
Provider firewall reminder: allow inbound 80/tcp, 7880/tcp, 7881/tcp,
and 50000-50100/udp. Do not expose backend port 8000 publicly.
EOF
