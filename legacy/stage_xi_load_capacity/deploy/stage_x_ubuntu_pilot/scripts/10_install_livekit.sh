#!/usr/bin/env bash
set -euo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
trap 'printf "%b\\n" "${RED}FATAL: LiveKit installation failed.${NC}" >&2' ERR

MANIFEST="/opt/byod/app/deploy/stage_x_ubuntu_pilot/manifest.yaml"
LIVEKIT_VERSION="1.9.11"
CUSTOM_TGZ="/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz"
CUSTOM_SHA="/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256"
FALLBACK_URL="https://github.com/livekit/livekit/releases/download/v1.9.11/livekit-server-v1.9.11-linux-amd64.tar.gz"
TMP_TGZ="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz"
TMP_EXTRACT_DIR="$(mktemp -d /tmp/livekit-extract-XXXXXX)"

cleanup() {
  rm -rf "$TMP_EXTRACT_DIR"
}
trap cleanup EXIT

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

if [[ -f "$CUSTOM_TGZ" ]]; then
  echo "Using custom artifact: $CUSTOM_TGZ"
  cp "$CUSTOM_TGZ" "$TMP_TGZ"
  if [[ ! -f "$CUSTOM_SHA" ]]; then
    echo "Missing checksum file: $CUSTOM_SHA"
    exit 1
  fi
  EXPECTED_SHA=$(awk '{print $1}' "$CUSTOM_SHA")
  ACTUAL_SHA=$(sha256sum "$TMP_TGZ" | awk '{print $1}')
  if [[ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]]; then
    echo "Checksum mismatch for custom LiveKit artifact"
    exit 1
  fi
else
  echo "Custom artifact not found, using fallback URL"
  curl -fL "$FALLBACK_URL" -o "$TMP_TGZ"
  printf "%b\n" "${YELLOW}WARNING: fallback artifact downloaded. Save checksum in manifest-controlled release bundle.${NC}"
fi

tar -xzf "$TMP_TGZ" -C "$TMP_EXTRACT_DIR"
if [[ ! -f "$TMP_EXTRACT_DIR/livekit-server" ]]; then
  echo "livekit-server binary not found in archive"
  exit 1
fi

install -m 0755 "$TMP_EXTRACT_DIR/livekit-server" /opt/byod/livekit/livekit-server
chown byod:byod /opt/byod/livekit/livekit-server

/opt/byod/livekit/livekit-server --version || true

printf "%b\n" "${CYAN}SUCCESS: LiveKit ${LIVEKIT_VERSION} installed. Manifest reference: ${MANIFEST}${NC}"
