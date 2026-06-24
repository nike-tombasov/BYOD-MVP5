#!/usr/bin/env bash
set -u

DIAG_DIR="/opt/byod/diagnostics"
SINCE="10 minutes ago"
LABEL=""
OUT_DIR="$DIAG_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<USAGE
Usage: sudo bash $0 [--since "15 minutes ago"] [--label LABEL] [--out-dir DIR]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE="${2:-}"; shift 2 ;;
    --label) LABEL="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

safe_label() { local value="$1"; value="${value//[^A-Za-z0-9_.-]/_}"; printf '%s' "$value"; }
mkdir -p "$OUT_DIR"
chmod 750 "$OUT_DIR" 2>/dev/null || true
STAMP="$(date +%Y%m%d_%H%M%S)"
LABEL_PART=""
[[ -n "$LABEL" ]] && LABEL_PART="_$(safe_label "$LABEL")"
OUT_FILES=()

path_for() {
  local base="$1" ext="$2" path
  path="${OUT_DIR}/${base}_${STAMP}${LABEL_PART}.${ext}"
  if [[ -e "$path" ]]; then
    path="${OUT_DIR}/${base}_${STAMP}${LABEL_PART}_$RANDOM.${ext}"
  fi
  printf '%s' "$path"
}

remember() { OUT_FILES+=("$1"); }

collect_journal() {
  local unit="$1" out="$2"
  remember "$out"
  {
    echo "timestamp_local=$(date -Is)"
    echo "timestamp_utc=$(date -u -Is)"
    echo "unit=$unit since=$SINCE"
    echo
    journalctl -u "$unit" --since "$SINCE" --no-pager 2>&1 || echo "WARNING: failed to collect $unit journal since $SINCE"
  } >"$out"
  if [[ ! -s "$out" ]]; then
    echo "WARNING: $unit journal output was empty" >"$out"
  fi
}

collect_file_tail() {
  local src="$1" out="$2" lines="${3:-1000}"
  remember "$out"
  {
    echo "timestamp_local=$(date -Is)"
    echo "timestamp_utc=$(date -u -Is)"
    echo "source=$src lines=$lines"
    echo
    if [[ -r "$src" ]]; then
      tail -n "$lines" "$src"
    else
      echo "WARNING: $src is missing or unreadable"
    fi
  } >"$out"
}

collect_jsonl_glob_tail() {
  local pattern="$1" out="$2" lines="${3:-1000}"
  remember "$out"
  {
    echo "# timestamp_local=$(date -Is)"
    echo "# timestamp_utc=$(date -u -Is)"
    echo "# source_glob=$pattern lines=$lines"
    shopt -s nullglob
    local files=( $pattern )
    shopt -u nullglob
    if [[ ${#files[@]} -eq 0 ]]; then
      echo "WARNING: no files matched $pattern"
    else
      tail -n "$lines" "${files[@]}" 2>&1 || echo "WARNING: failed to tail $pattern"
    fi
  } >"$out"
}

BACKEND_TAIL="$(path_for backend_tail txt)"
LIVEKIT_TAIL="$(path_for livekit_tail txt)"
NGINX_ACCESS="$(path_for nginx_access_tail txt)"
NGINX_WS="$(path_for nginx_ws_listener_access_tail txt)"
NGINX_ERROR="$(path_for nginx_error_tail txt)"
NGINX_ERROR_INTERESTING="$(path_for nginx_error_interesting_tail txt)"
CONNECTIONS="$(path_for backend_connections_tail jsonl)"
EVENTS="$(path_for backend_events_tail jsonl)"
SYSTEM_LIMITS="$(path_for system_limits_snapshot txt)"
SOCKETS="$(path_for socket_snapshot txt)"

collect_journal byod-backend "$BACKEND_TAIL"
collect_journal byod-livekit "$LIVEKIT_TAIL"
collect_file_tail /var/log/nginx/access.log "$NGINX_ACCESS" 1000
remember "$NGINX_WS"
if [[ -r /var/log/nginx/access.log ]]; then
  tail -n 1000 /var/log/nginx/access.log | grep '/ws/listener' >"$NGINX_WS" || true
  [[ -s "$NGINX_WS" ]] || echo "WARNING: no /ws/listener rows in last 1000 nginx access lines" >"$NGINX_WS"
else
  echo "WARNING: /var/log/nginx/access.log is missing or unreadable" >"$NGINX_WS"
fi
collect_file_tail /var/log/nginx/error.log "$NGINX_ERROR" 1000
remember "$NGINX_ERROR_INTERESTING"
if [[ -r /var/log/nginx/error.log ]]; then
  tail -n 1000 /var/log/nginx/error.log | grep -Ei 'error|upstream|connect|reset|closed|timeout|refused|too many|worker_connections' >"$NGINX_ERROR_INTERESTING" || true
  [[ -s "$NGINX_ERROR_INTERESTING" ]] || echo "WARNING: no interesting nginx error rows in last 1000 lines" >"$NGINX_ERROR_INTERESTING"
else
  echo "WARNING: /var/log/nginx/error.log is missing or unreadable" >"$NGINX_ERROR_INTERESTING"
fi
collect_jsonl_glob_tail '/opt/byod/backend_data/connections_log_*.jsonl' "$CONNECTIONS" 1000
collect_jsonl_glob_tail '/opt/byod/backend_data/events_log_*.jsonl' "$EVENTS" 1000

remember "$SYSTEM_LIMITS"
{
  echo "timestamp_local=$(date -Is)"
  echo "timestamp_utc=$(date -u -Is)"
  echo '--- systemd nofile limits ---'
  systemctl show nginx -p LimitNOFILE 2>&1 || true
  systemctl show byod-backend -p LimitNOFILE 2>&1 || true
  systemctl show byod-livekit -p LimitNOFILE 2>&1 || true
  echo '--- kernel limits ---'
  sysctl fs.file-max fs.nr_open net.core.somaxconn net.ipv4.ip_local_port_range 2>&1 || true
  echo '--- process limits ---'
  prlimit --pid "$(pidof nginx 2>/dev/null | awk '{print $1}')" 2>&1 || echo 'WARNING: nginx pid unavailable'
  prlimit --pid "$(pidof byod-backend 2>/dev/null | awk '{print $1}')" 2>&1 || echo 'WARNING: byod-backend pid unavailable'
  prlimit --pid "$(pidof livekit-server 2>/dev/null | awk '{print $1}')" 2>&1 || echo 'WARNING: livekit pid unavailable'
} >"$SYSTEM_LIMITS"

remember "$SOCKETS"
{
  echo "timestamp_local=$(date -Is)"
  echo "timestamp_utc=$(date -u -Is)"
  echo '--- ss summary ---'
  ss -s 2>&1 || true
  echo '--- listening tcp/udp ---'
  ss -lntup 2>&1 || true
  echo '--- port 80 connections ---'
  ss -tan '( sport = :80 or dport = :80 )' 2>&1 || true
  echo '--- time-wait count ---'
  ss -tan state time-wait 2>/dev/null | wc -l || true
  echo '--- established count ---'
  ss -tan state established 2>/dev/null | wc -l || true
} >"$SOCKETS"

if [[ -x "${SCRIPT_DIR}/72_metrics_snapshot.sh" ]]; then
  SNAPSHOT_ARGS=(--out-dir "$OUT_DIR")
  [[ -n "$LABEL" ]] && SNAPSHOT_ARGS+=(--label "$LABEL")
  if bash "${SCRIPT_DIR}/72_metrics_snapshot.sh" "${SNAPSHOT_ARGS[@]}"; then
    :
  else
    echo "WARNING: metrics snapshot helper reported unavailable" >&2
  fi
else
  echo "WARNING: missing ${SCRIPT_DIR}/72_metrics_snapshot.sh" >&2
fi

echo "Collected diagnostic files:"
printf '  %s\n' "${OUT_FILES[@]}"
