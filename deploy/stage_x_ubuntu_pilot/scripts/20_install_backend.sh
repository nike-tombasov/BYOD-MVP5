#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

rm -rf /opt/byod/app/backend
mkdir -p /opt/byod/app
cp -r "$REPO_ROOT/src/backend" /opt/byod/app/backend
cp "$REPO_ROOT/src/requirements.txt" /opt/byod/app/requirements.txt
cp -r "$REPO_ROOT/deploy" /opt/byod/app/deploy

python3.11 -m venv /opt/byod/app/.venv
/opt/byod/app/.venv/bin/pip install --upgrade pip
/opt/byod/app/.venv/bin/pip install -r /opt/byod/app/requirements.txt

install -m 0640 "$REPO_ROOT/.env.example" /opt/byod/config/backend.env
chown -R byod:byod /opt/byod/app /opt/byod/config/backend.env

echo "Backend installed. Edit /opt/byod/config/backend.env before start."
