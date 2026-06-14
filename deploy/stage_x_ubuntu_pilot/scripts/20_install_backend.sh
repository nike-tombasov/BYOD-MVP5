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
cp "$REPO_ROOT/src/backend/requirements.txt" /opt/byod/app/backend-requirements.txt
cp -r "$REPO_ROOT/deploy" /opt/byod/app/deploy

python3 -m venv /opt/byod/app/.venv
/opt/byod/app/.venv/bin/pip install --upgrade pip
/opt/byod/app/.venv/bin/pip install -r /opt/byod/app/backend-requirements.txt
(
  cd /opt/byod/app
  /opt/byod/app/.venv/bin/python -c 'import backend.main'
)

if [[ ! -f /opt/byod/config/backend.env ]]; then
  install -m 0640 "$REPO_ROOT/.env.example" /opt/byod/config/backend.env
fi

if [[ ! -f /opt/byod/config/livekit.yaml ]]; then
  install -m 0640 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/config/livekit.yaml" /opt/byod/config/livekit.yaml
fi

chown -R byod:byod /opt/byod/app /opt/byod/config/backend.env /opt/byod/config/livekit.yaml

echo "Backend installed. Edit /opt/byod/config/backend.env and /opt/byod/config/livekit.yaml before start."
