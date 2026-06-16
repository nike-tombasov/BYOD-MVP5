#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="byod-metrics-analyzer.service"
METRICS_DIR="/opt/byod/metrics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER_PATH="${SCRIPT_DIR}/metrics_analyzer.py"
INTERVAL_SEC="120"

usage() {
  cat <<EOF
Usage: sudo bash $0 start [--interval-sec 120]
       sudo bash $0 stop
       sudo bash $0 status
EOF
}

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root: sudo bash $0 $*" >&2
    exit 1
  fi
}

write_unit() {
  mkdir -p "${METRICS_DIR}"
  chown byod:byod "${METRICS_DIR}" 2>/dev/null || true
  chmod 750 "${METRICS_DIR}"
  cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=BYOD metrics analyzer
After=network-online.target byod-backend.service byod-livekit.service nginx.service
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 ${HELPER_PATH} --interval-sec ${INTERVAL_SEC}
Restart=on-failure
RestartSec=5
WorkingDirectory=${SCRIPT_DIR}

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
}

ACTION="${1:-}"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval-sec)
      INTERVAL_SEC="${2:-}"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

case "${ACTION}" in
  start)
    require_root "$@"
    if [[ ! -r "${HELPER_PATH}" ]]; then
      echo "Missing helper: ${HELPER_PATH}" >&2
      exit 1
    fi
    if ! [[ "${INTERVAL_SEC}" =~ ^[0-9]+$ ]] || [[ "${INTERVAL_SEC}" -lt 1 ]]; then
      echo "--interval-sec must be a positive integer" >&2
      exit 1
    fi
    write_unit
    systemctl enable "${SERVICE_NAME}" >/dev/null
    systemctl restart "${SERVICE_NAME}"
    systemctl status "${SERVICE_NAME}" --no-pager -l
    echo "Metrics output: ${METRICS_DIR}"
    ;;
  stop)
    require_root "$@"
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" >/dev/null 2>&1 || true
    echo "Stopped ${SERVICE_NAME}"
    ;;
  status)
    systemctl status "${SERVICE_NAME}" --no-pager -l || true
    echo "Metrics output: ${METRICS_DIR}"
    ;;
  *)
    usage
    exit 2
    ;;
esac
