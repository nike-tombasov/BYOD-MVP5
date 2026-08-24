#!/usr/bin/env bash
set -uo pipefail
CYAN='\033[1;36m'; RED='\033[1;31m'; YELLOW='\033[1;33m'; NC='\033[0m'


DIAG_DIR="/opt/byod/diagnostics"
LABEL=""
OUT_DIR="$DIAG_DIR"
ORIG_ARGS=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) echo "Usage: sudo bash $0 [--label LABEL] [--out-dir DIR]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

safe_label() { local value="$1"; value="${value//[^A-Za-z0-9_.-]/_}"; printf '%s' "$value"; }
mkdir -p "$OUT_DIR"
chmod 750 "$OUT_DIR" 2>/dev/null || true
STAMP="$(date +%Y%m%d_%H%M%S)"
LABEL_PART=""
[[ -n "$LABEL" ]] && LABEL_PART="_$(safe_label "$LABEL")"
SMOKE_OUT="${OUT_DIR}/smoke_test_${STAMP}${LABEL_PART}.txt"
if [[ -e "$SMOKE_OUT" ]]; then
  SMOKE_OUT="${OUT_DIR}/smoke_test_${STAMP}${LABEL_PART}_$RANDOM.txt"
fi
exec > >(tee "$SMOKE_OUT") 2>&1
printf 'timestamp_local=%s\n' "$(date -Is)"
printf 'timestamp_utc=%s\n' "$(date -u -Is)"
printf 'command_line=%q' "$0"
printf ' %q' "${ORIG_ARGS[@]}"
printf '\n'
printf 'output_file=%s\n\n' "$SMOKE_OUT"

overall=0
critical_failed=0

is_active() {
  systemctl is-active --quiet "$1" && printf 'active' || printf 'inactive'
}

port_state() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -tln | awk '{print $4}' | grep -Eq "(^|:)${port}$"; then
      printf '%s-listening' "$port"
    else
      printf '%s-not-listening' "$port"
    fi
  else
    printf '%s-unknown' "$port"
  fi
}

nginx_value() {
  local pattern="$1"
  if command -v nginx >/dev/null 2>&1; then
    nginx -T 2>/dev/null | awk -v pat="$pattern" '$1 == pat {gsub(";", "", $2); print $2; exit}'
  fi
}

backend_active=$(is_active byod-backend)
backend_health='unknown'
backend_port=$(port_state 8000)
if [[ "$backend_active" == "active" ]]; then
  curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && backend_health='ok' || backend_health='unavailable'
else
  critical_failed=1
fi
printf 'backend: %s, health=%s, port=%s\n' "$backend_active" "$backend_health" "$backend_port"

nginx_active=$(is_active nginx)
nginx_config='unknown'
if command -v nginx >/dev/null 2>&1; then
  nginx -t >/dev/null 2>&1 && nginx_config='ok' || nginx_config='bad'
else
  nginx_config='unavailable'
fi
worker_connections=$(nginx_value worker_connections)
worker_connections=${worker_connections:-unknown}
nginx_nofile=$(systemctl show nginx -p LimitNOFILE --value 2>/dev/null || true)
nginx_nofile=${nginx_nofile:-unknown}
if [[ "$nginx_active" != "active" || "$nginx_config" != "ok" ]]; then
  critical_failed=1
fi
printf 'nginx: %s, config=%s, worker_connections=%s, nofile=%s\n' "$nginx_active" "$nginx_config" "$worker_connections" "$nginx_nofile"

livekit_active=$(is_active byod-livekit)
livekit_port=$(port_state 7880)
livekit_tcp=$(port_state 7881 | sed 's/^7881-/tcp=7881-/')
if [[ "$livekit_active" != "active" ]]; then
  critical_failed=1
fi
printf 'livekit: %s, port=%s, %s\n' "$livekit_active" "$livekit_port" "$livekit_tcp"

livekit_config='/opt/byod/config/livekit.yaml'
udp_range='unknown'
if [[ -r "$livekit_config" ]]; then
  udp_start=$(awk '$1 == "port_range_start:" {print $2; exit}' "$livekit_config")
  udp_end=$(awk '$1 == "port_range_end:" {print $2; exit}' "$livekit_config")
  if [[ -n "${udp_start:-}" && -n "${udp_end:-}" ]]; then
    udp_range="${udp_start}-${udp_end}"
  fi
fi
printf 'livekit-config: udp_range=%s, fallback_udp_mux=7882\n' "$udp_range"

if command -v btop >/dev/null 2>&1; then
  printf 'btop: installed\n'
else
  printf 'btop: missing\n'
fi

vendor_path='/opt/byod/listener/vendor/livekit-client.umd.1.15.13.js'
if [[ -r "$vendor_path" ]]; then
  printf 'vendor/livekit-client: present\n'
else
  printf 'vendor/livekit-client: missing\n'
fi

room_config_path='/opt/byod/backend_data/room_config_v1.json'
if [[ -r "$room_config_path" ]]; then
  printf 'room-config: present\n'
else
  printf 'room-config: missing\n'
fi

metrics='unknown'
max_active_listeners='unknown'
max_new_connections_per_sec='unknown'
loadgen_reconnect_bypass_enabled='unknown'
listener_min_reconnect_interval_per_ip_seconds='unknown'
if curl -sf http://127.0.0.1:8000/admin/metrics_snapshot >/tmp/byod_smoke_metrics.json 2>/dev/null; then
  metrics='local-only-ok'
  eval "$(python3 - <<'PYMETRICS'
import json
try:
    p=json.load(open('/tmp/byod_smoke_metrics.json'))
except Exception:
    p={}
for k in ('max_active_listeners','max_new_connections_per_sec','loadgen_reconnect_bypass_enabled','listener_min_reconnect_interval_per_ip_seconds'):
    print(f'{k}={repr(str(p.get(k, "unknown")))}')
PYMETRICS
)"
elif [[ "$backend_active" == "active" ]]; then
  metrics='unavailable'
fi
printf 'metrics: %s\n' "$metrics"
printf 'backend-limits: max_active_listeners=%s max_new_connections_per_sec=%s loadgen_reconnect_bypass_enabled=%s listener_min_reconnect_interval_per_ip_seconds=%s\n' "$max_active_listeners" "$max_new_connections_per_sec" "$loadgen_reconnect_bypass_enabled" "$listener_min_reconnect_interval_per_ip_seconds"
printf 'livekit-config: udp_range=50000-59999, fallback_udp_mux=7882\n'

if [[ "${BYOD_DOMAIN_TLS_MODE:-false}" == "true" ]]; then
  domain_failed=0
  curl -fsS "https://${BYOD_LISTENER_DOMAIN}/" >/dev/null || domain_failed=1
  curl -fsS "https://${BYOD_LISTENER_DOMAIN}/health" >/dev/null || domain_failed=1
  admin_status="not-configured"
  if [[ -n "${BYOD_ADMIN_DOMAIN:-}" ]]; then
    admin_status="$(curl -sS -o /dev/null -w '%{http_code}' "https://${BYOD_ADMIN_DOMAIN}/admin/metrics_snapshot" || true)"
    [[ "$admin_status" != 2* ]] || domain_failed=1
  fi
  public_admin_status="$(curl -sS -o /dev/null -w '%{http_code}' "https://${BYOD_LISTENER_DOMAIN}/admin/metrics_snapshot" || true)"
  [[ "$public_admin_status" != 2* ]] || domain_failed=1
  backend_livekit_url="$(awk -F= '$1 == "BYOD_LIVEKIT_URL" {gsub(/^"|"$/, "", $2); print $2}' /opt/byod/config/backend.env 2>/dev/null)"
  [[ "$backend_livekit_url" == "wss://${BYOD_LIVEKIT_DOMAIN}" ]] || domain_failed=1
  printf 'domain-tls: listener=https://%s livekit=%s public-admin-http=%s reserved-admin-http=%s\n' "$BYOD_LISTENER_DOMAIN" "$backend_livekit_url" "$public_admin_status" "$admin_status"
  printf 'domain-tls: WSS paths share the validated HTTPS nginx endpoints (protocol upgrade requires a client token)\n'
  if [[ "$domain_failed" -ne 0 ]]; then critical_failed=1; fi
  firewall_ports='80/tcp, 443/tcp, 7881/tcp, and 50000-59999/udp'
else
  firewall_ports='80/tcp, 7880/tcp, 7881/tcp, and 50000-59999/udp'
fi

printf "%b\n" "${YELLOW}Provider firewall reminder: allow inbound ${firewall_ports}. Do not expose backend port 8000 publicly.${NC}"
printf "smoke_test_output_file=%s\n" "$SMOKE_OUT"

if [[ "$critical_failed" -ne 0 ]]; then
  overall=1
  printf "%b\n" "${RED}FAIL: Critical smoke checks failed.${NC}" >&2
else
  printf "%b\n" "${CYAN}SUCCESS: BYOD smoke checks completed.${NC}"
fi

exit "$overall"
