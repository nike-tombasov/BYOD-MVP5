#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}FATAL: Listener installation failed.${NC}" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENDOR_NAME="livekit-client.umd.1.15.13.js"
VENDOR_SOURCE="$REPO_ROOT/src/listener/vendor/$VENDOR_NAME"

if [[ ! -f "$VENDOR_SOURCE" ]]; then
  printf "%b\n" "${RED}Missing LiveKit browser SDK vendor file. Put livekit-client.umd.1.15.13.js into src/listener/vendor before deploy.${NC}" >&2
  exit 1
fi

rm -rf /opt/byod/listener/*
cp -r "$REPO_ROOT/src/listener/." /opt/byod/listener/
chown -R byod:byod /opt/byod/listener
chmod -R 0755 /opt/byod/listener
sudo -u www-data test -r /opt/byod/listener/vendor/livekit-client.umd.1.15.13.js

printf "%b\n" "${CYAN}SUCCESS: Listener static files and pinned LiveKit browser SDK installed.${NC}"
