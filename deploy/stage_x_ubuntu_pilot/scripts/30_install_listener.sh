#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

rm -rf /opt/byod/listener/*
cp -r "$REPO_ROOT/src/listener/." /opt/byod/listener/
chown -R byod:byod /opt/byod/listener
chmod -R 0755 /opt/byod/listener

echo "Listener static files installed."
