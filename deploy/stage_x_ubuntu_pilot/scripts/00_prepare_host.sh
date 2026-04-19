#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3.11 python3.11-venv python3-pip nginx curl ca-certificates

id -u byod >/dev/null 2>&1 || useradd --system --home /opt/byod --shell /usr/sbin/nologin byod

for d in /opt/byod/app /opt/byod/config /opt/byod/livekit /opt/byod/listener /opt/byod/backend_data /opt/byod/logs /opt/byod/releases; do
  mkdir -p "$d"
done

chown -R byod:byod /opt/byod
chmod 750 /opt/byod /opt/byod/config /opt/byod/backend_data /opt/byod/logs

echo "Host prepared."
