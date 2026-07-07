#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}FATAL: Listener installation failed.${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENDOR_NAME="livekit-client.umd.1.15.13.js"
VENDOR_SOURCE="$REPO_ROOT/src/listener/vendor/$VENDOR_NAME"
VENDOR_DEST="/opt/byod/listener/vendor/$VENDOR_NAME"

if [[ -f "$VENDOR_SOURCE" ]]; then
  printf "%b\n" "${CYAN}vendor/livekit-client: source present; local pinned vendor will be deployed.${NC}"
else
  printf "%b\n" "${YELLOW}WARNING: local pinned vendor file is missing at src/listener/vendor/$VENDOR_NAME.${NC}" >&2
  printf "%b\n" "${YELLOW}WARNING: Listener install will continue; browser should fall back to CDN.${NC}" >&2
  printf "%b\n" "${YELLOW}WARNING: After Listener install, operator can install local runtime vendor with scripts/66_install_livekit_vendor_from_tmp.sh.${NC}" >&2
fi

rm -rf /opt/byod/listener/*
cp -r "$REPO_ROOT/src/listener/." /opt/byod/listener/
chown -R byod:byod /opt/byod/listener
chmod -R 0755 /opt/byod/listener

if sudo -u www-data test -r "$VENDOR_DEST"; then
  echo "vendor/livekit-client: present"
else
  echo "vendor/livekit-client: missing, CDN fallback expected"
fi

printf "%b\n" "${CYAN}SUCCESS: Listener static files installed.${NC}"
