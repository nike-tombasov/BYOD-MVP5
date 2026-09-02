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
BYOD_DOMAIN_TLS_MODE="${BYOD_DOMAIN_TLS_MODE:-false}"
case "${BYOD_DOMAIN_TLS_MODE,,}" in
  true) BYOD_DOMAIN_TLS_MODE=true ;;
  false) BYOD_DOMAIN_TLS_MODE=false ;;
  *) fatal "BYOD_DOMAIN_TLS_MODE must be true or false" ;;
esac
normalized_public_origin="${BYOD_PUBLIC_ORIGIN%/}"
if [[ "$normalized_public_origin" != "$BYOD_PUBLIC_ORIGIN" ]]; then
  warn "BYOD_PUBLIC_ORIGIN had a trailing slash; normalized to $normalized_public_origin."
  BYOD_PUBLIC_ORIGIN="$normalized_public_origin"
fi
validate_hostname() {
  local name="$1" value="${!1:-}"
  [[ "$value" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$ ]] ||
    fatal "$name must be a hostname only (no scheme, port, path, or wildcard)"
}
if [[ "$BYOD_DOMAIN_TLS_MODE" == true ]]; then
  for n in BYOD_LISTENER_DOMAIN BYOD_LIVEKIT_DOMAIN BYOD_TLS_EMAIL; do require_var "$n"; done
  validate_hostname BYOD_LISTENER_DOMAIN
  validate_hostname BYOD_LIVEKIT_DOMAIN
  [[ -z "${BYOD_ADMIN_DOMAIN:-}" ]] || validate_hostname BYOD_ADMIN_DOMAIN
  [[ "$BYOD_TLS_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || fatal "BYOD_TLS_EMAIL must be a valid email address"
  [[ "$BYOD_PUBLIC_ORIGIN" == "https://$BYOD_LISTENER_DOMAIN" ]] || fatal "domain mode requires BYOD_PUBLIC_ORIGIN=https://$BYOD_LISTENER_DOMAIN (no path)"
  [[ "$BYOD_LIVEKIT_URL" == "wss://$BYOD_LIVEKIT_DOMAIN" ]] || fatal "domain mode requires BYOD_LIVEKIT_URL=wss://$BYOD_LIVEKIT_DOMAIN (no path)"
fi
[[ "$BYOD_BACKEND_PORT" =~ ^[0-9]+$ ]] || fatal "BYOD_BACKEND_PORT must be an integer"
[[ "$BYOD_PUBLIC_ORIGIN" =~ ^https?:// ]] || fatal "BYOD_PUBLIC_ORIGIN must start with http:// or https://"
[[ "$BYOD_LIVEKIT_URL" =~ ^wss?:// ]] || fatal "BYOD_LIVEKIT_URL must start with ws:// or wss://"
BYOD_DEFAULT_PIN="${BYOD_DEFAULT_PIN:-123456}"
BYOD_ROOM_INPUT_PATH="${BYOD_ROOM_INPUT_PATH:-/tmp/room_input.json}"
BYOD_LIVEKIT_TGZ_PATH="${BYOD_LIVEKIT_TGZ_PATH:-/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz}"
BYOD_LIVEKIT_SHA256_PATH="${BYOD_LIVEKIT_SHA256_PATH:-/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256}"
BYOD_LISTENER_VENDOR_PATH="${BYOD_LISTENER_VENDOR_PATH:-/tmp/livekit-client.umd.1.15.13.js}"
BYOD_ENABLE_BACKEND_STRESS_TEST="${BYOD_ENABLE_BACKEND_STRESS_TEST:-false}"
case "${BYOD_ENABLE_BACKEND_STRESS_TEST,,}" in
  true|1|yes|on) BYOD_ENABLE_BACKEND_STRESS_TEST_NORMALIZED=true ;;
  false|0|no|off) BYOD_ENABLE_BACKEND_STRESS_TEST_NORMALIZED=false ;;
  *) fatal "BYOD_ENABLE_BACKEND_STRESS_TEST must be one of: true, false, 1, 0, yes, no, on, off" ;;
esac
BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS="${BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS:-2}"
[[ "$BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS" =~ ^[0-9]+$ ]] || fatal "BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS must be an integer >= 0"
BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE="${BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE:-}"
if [[ -n "$BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE" ]]; then
  [[ "$BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE" =~ ^[0-9]+$ ]] || fatal "BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE must be an integer >= 1 when set"
  [[ "$BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE" -ge 1 ]] || fatal "BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE must be >= 1 when set"
fi
export BYOD_DOMAIN_TLS_MODE BYOD_ENABLE_BACKEND_STRESS_TEST_NORMALIZED BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE
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
    'BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS': os.environ.get('BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS', '2'),
    'BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE': os.environ.get('BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE', ''),
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
print(f"room_import: room_name={a.get('room_name')} subsite_name={a.get('subsite_name')} target_capacity={a.get('target_capacity')} max_active_listeners={a.get('max_active_listeners')} max_new_connections_per_sec={a.get('max_new_connections_per_sec')} channels={a.get('channels')}")
PY
  rm -f "$response_file"
  ok "Room config imported through backend validation endpoint"
else
  warn "Room input file not found: $BYOD_ROOM_INPUT_PATH; clearing any persisted event alias."
  python3 - <<'PY_CLEAR_ALIAS'
import json, pathlib
path = pathlib.Path('/opt/byod/backend_data/room_config_v1.json')
if path.is_file():
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['subsite_name'] = None
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY_CLEAR_ALIAS
  systemctl restart byod-backend
  backend_ready=false
  for _ in {1..30}; do
    if curl -sf http://127.0.0.1:8000/health >/dev/null; then
      backend_ready=true
      break
    fi
    sleep 1
  done
  [[ "$backend_ready" == true ]] || fatal "Backend did not become healthy after clearing persisted subsite_name"
  ok "Backend restarted with no configured Listener alias"
fi

if [[ "$BYOD_DOMAIN_TLS_MODE" == true ]]; then
  step "Verify domain DNS and configure trusted TLS with the validated event alias"
  bash deploy/stage_x_ubuntu_pilot/scripts/30_domain_dns_preflight.sh
  bash deploy/stage_x_ubuntu_pilot/scripts/31_setup_domain_tls.sh
fi

if [[ "$BYOD_ENABLE_BACKEND_STRESS_TEST_NORMALIZED" == "true" ]]; then
  warn "BACKEND STRESS TEST PROFILE ENABLED: applying temporary backend admission/capacity overrides before smoke test."
  bash deploy/stage_x_ubuntu_pilot/scripts/68_apply_backend_stress_profile.sh
else
  ok "Backend stress test profile disabled; no stress drop-in applied."
fi

step "Run smoke test"
bash deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label one_deploy
smoke_path="$(find /opt/byod/diagnostics -maxdepth 1 -type f -name '*one_deploy*.txt' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1{print $2}')"

step "Summary"
printf 'backend_health=%s\n' "$(curl -sf http://127.0.0.1:8000/health 2>/dev/null || printf unavailable)"
printf 'nginx_status=%s\n' "$(systemctl is-active nginx 2>/dev/null || true)"
printf 'livekit_status=%s\n' "$(systemctl is-active byod-livekit 2>/dev/null || true)"
public_origin="${BYOD_PUBLIC_ORIGIN%/}"
printf 'listener_url=%s/\n' "$public_origin"
# Publisher UI's Server IP field uses the public-IP nginx route in VPS mode,
# never the Listener or LiveKit domain.
printf 'publisher_backend_url=ws://%s/ws/publisher\n' "$BYOD_VPS_PUBLIC_IP"
printf 'smoke_output_file=%s\n' "${smoke_path:-unknown}"
if [[ "$BYOD_DOMAIN_TLS_MODE" == true ]]; then
  warn "Provider firewall: allow 80/tcp, 443/tcp, 7881/tcp, 50000-59999/udp; do not expose 8000/tcp."
else
  warn "Provider firewall: allow 80/tcp, 7880/tcp, 7881/tcp, 50000-59999/udp; do not expose 8000/tcp."
fi
ok "BYOD VPS deploy completed."
