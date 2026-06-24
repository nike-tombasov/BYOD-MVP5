#!/usr/bin/env bash
set -uo pipefail

CYAN='\033[1;36m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ ${EUID} -ne 0 ]]; then
  printf "%b\n" "${RED}FATAL: Run as root: sudo bash $0${NC}" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUNDLE_DIR="/tmp/byod-diagnostics-${STAMP}"
REPORT="${BUNDLE_DIR}/diagnostics.txt"
mkdir -p "$BUNDLE_DIR"
chmod 0700 "$BUNDLE_DIR"

section() {
  printf '\n===== %s =====\n' "$1" | tee -a "$REPORT"
}

capture() {
  local title="$1"
  shift
  section "$title"
  "$@" 2>&1 | tee -a "$REPORT" || printf '[command unavailable or returned non-zero]\n' | tee -a "$REPORT"
}

sanitize_backend_env() {
  if [[ ! -r /opt/byod/config/backend.env ]]; then
    echo "backend.env not readable"
    return
  fi
  sed -E \
    -e 's/^([[:space:]]*(export[[:space:]]+)?BYOD_LIVEKIT_API_SECRET[[:space:]]*=).*/\1<REDACTED>/' \
    -e 's/^([[:space:]]*(export[[:space:]]+)?BYOD_DEFAULT_PIN[[:space:]]*=).*/\1<REDACTED>/' \
    /opt/byod/config/backend.env
}

sanitize_livekit_yaml() {
  if [[ ! -r /opt/byod/config/livekit.yaml ]]; then
    echo "livekit.yaml not readable"
    return
  fi
  awk '
    /^[[:space:]]*keys:[[:space:]]*$/ { print; in_keys=1; next }
    in_keys && /^[^[:space:]#]/ { in_keys=0 }
    in_keys && /^[[:space:]]*[^#][^:]*:/ {
      match($0, /^[[:space:]]*/)
      indent=substr($0, 1, RLENGTH)
      key=$0
      sub(/^[[:space:]]*/, "", key)
      sub(/:.*/, "", key)
      print indent "\"" key "\": \"<REDACTED>\""
      next
    }
    { print }
  ' /opt/byod/config/livekit.yaml
}

section "SCOPE"
printf 'This is the general deploy diagnostic bundle. For stress-test emergency tails use deploy/stage_x_ubuntu_pilot/scripts/71_collect_test_tails.sh; for local metrics snapshots use 72_metrics_snapshot.sh.\n' | tee -a "$REPORT"

capture "HOST" bash -c 'date -Is; hostname; uname -a'
capture "SYSTEMD STATUS" systemctl --no-pager --full status nginx byod-backend byod-livekit
capture "BACKEND JOURNAL (last 300)" journalctl --no-pager -u byod-backend -n 300
capture "LIVEKIT JOURNAL (last 300)" journalctl --no-pager -u byod-livekit -n 300
capture "NGINX JOURNAL (last 200)" journalctl --no-pager -u nginx -n 200

section "NGINX BYOD CONFIG"
nginx -T 2>&1 | awk '
  /configuration file .*byod-listener\.conf/ { show=1 }
  show { print }
  show && /^}/ { exit }
' | tee -a "$REPORT" || printf '[nginx configuration unavailable]\n' | tee -a "$REPORT"

capture "LISTENING PORTS 80/8000/7880/7881" bash -c "ss -lntup | awk 'NR == 1 || /:80 |:8000 |:7880 |:7881 /'"
capture "UFW STATUS" ufw status verbose

section "SANITIZED backend.env"
sanitize_backend_env | tee -a "$REPORT"
section "SANITIZED livekit.yaml"
sanitize_livekit_yaml | tee -a "$REPORT"

capture "LISTENER FILES" bash -c 'ls -lah /opt/byod/listener; echo; ls -lah /opt/byod/listener/vendor'
capture "WWW-DATA READ TESTS" bash -c '
  for path in \
    /opt/byod/listener/index.html \
    /opt/byod/listener/listener.js \
    /opt/byod/listener/vendor/livekit-client.umd.1.15.13.js
  do
    if sudo -u www-data test -r "$path"; then
      echo "READABLE $path"
    else
      echo "NOT_READABLE $path"
    fi
  done
'
capture "CONNECTION JSONL TAIL" bash -c 'tail -n 200 /opt/byod/backend_data/connections_log_*.jsonl'
capture "EVENT JSONL TAIL" bash -c 'tail -n 300 /opt/byod/backend_data/events_log_*.jsonl'
capture "HTTP HEALTH" curl -i --max-time 10 http://127.0.0.1/health
capture "HTTP DOCS" curl -i --max-time 10 http://127.0.0.1/docs

cp "$REPORT" "${BUNDLE_DIR}/diagnostics-${STAMP}.txt"
chmod -R go-rwx "$BUNDLE_DIR"

printf "\n%b\n" "${CYAN}DIAGNOSTICS COMPLETE${NC}"
printf "%b\n" "${CYAN}Bundle: ${BUNDLE_DIR}${NC}"
printf "%b\n" "${CYAN}Report: ${REPORT}${NC}"
printf "%b\n" "${YELLOW}Secrets were redacted; review the report before sharing it.${NC}"
