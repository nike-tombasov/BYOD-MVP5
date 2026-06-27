#!/usr/bin/env bash
set -euo pipefail
BLUE='\033[1;34m'; CYAN='\033[1;36m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
step(){ printf "%b\n" "${BLUE}==> $*${NC}"; }
ok(){ printf "%b\n" "${GREEN}OK: $*${NC}"; }
warn(){ printf "%b\n" "${YELLOW}WARNING: $*${NC}"; }
fatal(){ printf "%b\n" "${RED}FATAL: $*${NC}" >&2; exit 1; }
trap 'fatal "one-command deploy failed near line $LINENO"' ERR

[[ ${EUID} -eq 0 ]] || fatal "Run as root: sudo bash $0 /tmp/vps_config.env"
CONFIG_PATH="${1:-${BYOD_VPS_CONFIG:-/tmp/vps_config.env}}"
[[ -r "$CONFIG_PATH" ]] || fatal "VPS config is not readable: $CONFIG_PATH"
if grep -q $'\r' "$CONFIG_PATH"; then
  warn "CRLF detected in $CONFIG_PATH; converting to LF before source."
  sed -i 's/\r$//' "$CONFIG_PATH"
fi
# shellcheck disable=SC1090
set -a; source "$CONFIG_PATH"; set +a

require_var(){ local n="$1"; [[ -n "${!n:-}" ]] || fatal "Missing required config value: $n"; }
for n in BYOD_REPO_URL BYOD_REPO_BRANCH BYOD_VPS_PUBLIC_IP BYOD_PUBLIC_ORIGIN BYOD_LIVEKIT_URL BYOD_LIVEKIT_API_KEY BYOD_LIVEKIT_API_SECRET BYOD_BACKEND_HOST BYOD_BACKEND_PORT; do require_var "$n"; done
[[ "$BYOD_BACKEND_PORT" =~ ^[0-9]+$ ]] || fatal "BYOD_BACKEND_PORT must be an integer"
[[ "$BYOD_PUBLIC_ORIGIN" =~ ^https?:// ]] || fatal "BYOD_PUBLIC_ORIGIN must start with http:// or https://"
[[ "$BYOD_LIVEKIT_URL" =~ ^wss?:// ]] || fatal "BYOD_LIVEKIT_URL must start with ws:// or wss://"
BYOD_DEFAULT_PIN="${BYOD_DEFAULT_PIN:-123456}"
BYOD_ROOM_INPUT_PATH="${BYOD_ROOM_INPUT_PATH:-/tmp/room_input.json}"
BYOD_LIVEKIT_TGZ_PATH="${BYOD_LIVEKIT_TGZ_PATH:-/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz}"
BYOD_LIVEKIT_SHA256_PATH="${BYOD_LIVEKIT_SHA256_PATH:-/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256}"
BYOD_LISTENER_VENDOR_PATH="${BYOD_LISTENER_VENDOR_PATH:-/tmp/livekit-client.umd.1.15.13.js}"
redacted_secret="${BYOD_LIVEKIT_API_SECRET:0:4}…redacted…${BYOD_LIVEKIT_API_SECRET: -4}"
ok "Loaded config: repo_branch=${BYOD_REPO_BRANCH}, origin=${BYOD_PUBLIC_ORIGIN}, livekit=${BYOD_LIVEKIT_URL}, api_key=${BYOD_LIVEKIT_API_KEY}, api_secret=${redacted_secret}"

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

step "Prepare host"
bash deploy/stage_x_ubuntu_pilot/scripts/00_prepare_host.sh

step "Copy and verify LiveKit release artifact"
[[ -s "$BYOD_LIVEKIT_TGZ_PATH" ]] || fatal "Required LiveKit archive missing or empty: $BYOD_LIVEKIT_TGZ_PATH"
[[ -s "$BYOD_LIVEKIT_SHA256_PATH" ]] || fatal "Required LiveKit checksum missing or empty: $BYOD_LIVEKIT_SHA256_PATH"
install -d -o byod -g byod -m 0755 /opt/byod/releases
cp "$BYOD_LIVEKIT_TGZ_PATH" /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz
cp "$BYOD_LIVEKIT_SHA256_PATH" /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256
chown byod:byod /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256
expected_sha="$(awk '{print $1; exit}' /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256)"
actual_sha="$(sha256sum /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz | awk '{print $1}')"
[[ "$expected_sha" == "$actual_sha" ]] || fatal "LiveKit checksum mismatch before install"
ok "LiveKit checksum verified before install"

step "Install LiveKit, backend, and listener"
bash deploy/stage_x_ubuntu_pilot/scripts/10_install_livekit.sh
bash deploy/stage_x_ubuntu_pilot/scripts/20_install_backend.sh
bash deploy/stage_x_ubuntu_pilot/scripts/30_install_listener.sh

step "Generate runtime configuration"
install -d -o byod -g byod -m 0750 /opt/byod/config
python3 - <<'PY_BACKEND' > /opt/byod/config/backend.env
import os

def q(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

values = {
    'BYOD_LIVEKIT_URL': os.environ['BYOD_LIVEKIT_URL'],
    'BYOD_LIVEKIT_API_KEY': os.environ['BYOD_LIVEKIT_API_KEY'],
    'BYOD_LIVEKIT_API_SECRET': os.environ['BYOD_LIVEKIT_API_SECRET'],
    'BYOD_BACKEND_HOST': os.environ['BYOD_BACKEND_HOST'],
    'BYOD_BACKEND_PORT': os.environ['BYOD_BACKEND_PORT'],
    'BYOD_CORS_ALLOWED_ORIGIN': os.environ['BYOD_PUBLIC_ORIGIN'],
    'BYOD_DATA_DIR': '/opt/byod/backend_data',
    'BYOD_ROOM_CONFIG_PATH': '/opt/byod/backend_data/room_config_v1.json',
    'BYOD_RUNTIME_STATE_PATH': '/opt/byod/backend_data/runtime_state_v1.json',
    'BYOD_RECORDING_STATE_PATH': '/opt/byod/backend_data/recording_state_v1.json',
    'BYOD_DEFAULT_PIN': os.environ.get('BYOD_DEFAULT_PIN', '123456'),
}
for key, value in values.items():
    print(f'{key}={q(value)}')
PY_BACKEND
python3 - <<'PY' > /opt/byod/config/livekit.yaml
import json, os
key=os.environ['BYOD_LIVEKIT_API_KEY']; secret=os.environ['BYOD_LIVEKIT_API_SECRET']
print('port: 7880')
print('bind_addresses: ["0.0.0.0"]')
print('rtc:')
print('  tcp_port: 7881')
print('  port_range_start: 50000')
print('  port_range_end: 59999')
print('  use_external_ip: true')
print('keys:')
print(f'  {json.dumps(key)}: {json.dumps(secret)}')
PY
sed -i 's/\r$//' /opt/byod/config/backend.env /opt/byod/config/livekit.yaml
chown byod:byod /opt/byod/config/backend.env /opt/byod/config/livekit.yaml
chmod 0640 /opt/byod/config/backend.env /opt/byod/config/livekit.yaml
ok "Generated /opt/byod/config/backend.env and /opt/byod/config/livekit.yaml"

step "Install optional Listener vendor"
if [[ -s "$BYOD_LISTENER_VENDOR_PATH" ]]; then
  bash deploy/stage_x_ubuntu_pilot/scripts/66_install_livekit_vendor_from_tmp.sh "$BYOD_LISTENER_VENDOR_PATH"
else
  warn "Listener vendor file missing or empty: $BYOD_LISTENER_VENDOR_PATH; continuing with CDN fallback."
fi

step "Enable and start services"
bash deploy/stage_x_ubuntu_pilot/scripts/40_enable_services.sh

step "Import optional room config"
if [[ -s "$BYOD_ROOM_INPUT_PATH" ]]; then
  response_file="$(mktemp /tmp/byod-room-import-XXXXXX.json)"
  curl -sf -F "file=@${BYOD_ROOM_INPUT_PATH};type=application/json" "http://127.0.0.1:8000/admin/import_json" -o "$response_file"
  python3 - "$response_file" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
if not p.get('ok'):
    print(json.dumps(p, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)
a=p.get('applied', {})
print(f"room_import: room_name={a.get('room_name')} target_capacity={a.get('target_capacity')} max_active_listeners={a.get('max_active_listeners')} max_new_connections_per_sec={a.get('max_new_connections_per_sec')} channels={a.get('channels')}")
PY
  rm -f "$response_file"
  ok "Room config imported through backend validation endpoint"
else
  warn "Room input file not found: $BYOD_ROOM_INPUT_PATH; continuing with default persisted room config."
fi

step "Run smoke test"
bash deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label one_deploy
smoke_path="$(find /opt/byod/diagnostics -maxdepth 1 -type f -name '*one_deploy*.txt' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1{print $2}')"

step "Summary"
printf 'backend_health=%s\n' "$(curl -sf http://127.0.0.1:8000/health 2>/dev/null || printf unavailable)"
printf 'nginx_status=%s\n' "$(systemctl is-active nginx 2>/dev/null || true)"
printf 'livekit_status=%s\n' "$(systemctl is-active byod-livekit 2>/dev/null || true)"
printf 'listener_url=%s/listener/\n' "$BYOD_PUBLIC_ORIGIN"
printf 'publisher_backend_url=http://127.0.0.1:${BYOD_BACKEND_PORT}\n'
printf 'smoke_output_file=%s\n' "${smoke_path:-unknown}"
warn "Provider firewall: allow 80/tcp, 7880/tcp, 7881/tcp, 50000-59999/udp; do not expose 8000/tcp."
ok "BYOD VPS deploy completed."
