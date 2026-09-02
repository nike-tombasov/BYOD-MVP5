#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}FATAL: Host preparation failed.${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx curl ca-certificates git btop

# The packaged default also claims server_name _ on port 80. BYOD owns the
# single default server, so remove only its enabled symlink (idempotently).
rm -f /etc/nginx/sites-enabled/default

id -u byod >/dev/null 2>&1 || useradd --system --home /opt/byod --shell /usr/sbin/nologin byod

for d in /opt/byod/app /opt/byod/config /opt/byod/livekit /opt/byod/listener /opt/byod/backend_data /opt/byod/logs /opt/byod/metrics /opt/byod/releases; do
  mkdir -p "$d"
done

chown -R byod:byod /opt/byod
chmod 755 /opt/byod
chmod 750 /opt/byod/config /opt/byod/backend_data /opt/byod/logs /opt/byod/metrics
chmod 755 /opt/byod/listener

printf "%b\n" "${CYAN}SUCCESS: Host prepared.${NC}"
