#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}livekit-vendor-install: failed${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0 [source_js]"
  exit 1
fi

SRC="${1:-/tmp/livekit-client.umd.1.15.13.js}"
DST="/opt/byod/listener/vendor/livekit-client.umd.1.15.13.js"
DST_DIR="$(dirname "$DST")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="${DST_DIR}/.livekit-client.umd.1.15.13.js.tmp.${STAMP}.$$"

if [[ ! -r "$SRC" ]]; then
  echo "vendor-source: missing-or-unreadable path=$SRC" >&2
  exit 1
fi
if [[ ! -s "$SRC" ]]; then
  echo "vendor-source: empty path=$SRC" >&2
  exit 1
fi

install -d -o www-data -g www-data -m 0755 "$DST_DIR"
cp "$SRC" "$TMP"
chown www-data:www-data "$TMP"
chmod 0644 "$TMP"
mv -f "$TMP" "$DST"

echo "vendor/livekit-client: installed path=$DST owner=www-data:www-data mode=0644"
echo "next-check: sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh"
printf "%b\n" "${CYAN}SUCCESS: LiveKit browser client vendor file installed from local VPS file.${NC}"
