#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}room-config-import: failed${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0 [source_json]"
  exit 1
fi

SRC="${1:-/tmp/room_config_v1.json}"
DST="/opt/byod/backend_data/room_config_v1.json"
DST_DIR="$(dirname "$DST")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="${DST_DIR}/.room_config_v1.json.tmp.${STAMP}.$$"

if [[ ! -r "$SRC" ]]; then
  echo "room-config-source: missing-or-unreadable path=$SRC" >&2
  exit 1
fi

python3 -m json.tool "$SRC" >/dev/null
echo "room-config-json: syntax=ok source=$SRC"

install -d -o byod -g byod -m 0750 "$DST_DIR"
if [[ -e "$DST" ]]; then
  BACKUP="${DST}.backup.${STAMP}"
  cp -a "$DST" "$BACKUP"
  echo "room-config-backup: path=$BACKUP"
else
  echo "room-config-backup: none-existing-destination"
fi

cp "$SRC" "$TMP"
chown byod:byod "$TMP"
chmod 0640 "$TMP"
mv -f "$TMP" "$DST"
echo "room-config-installed: path=$DST owner=byod:byod mode=0640"

systemctl restart byod-backend
echo "backend-restart: requested"

systemctl is-active --quiet byod-backend
echo "backend: active"

curl -sf http://127.0.0.1:8000/health >/dev/null
echo "backend-health: ok"

printf "%b\n" "${CYAN}SUCCESS: room config imported from local VPS file without SwaggerUI.${NC}"
