#!/usr/bin/env bash
set -u

DIAG_DIR="/opt/byod/diagnostics"
ENDPOINT="http://127.0.0.1:8000/admin/metrics_snapshot"
INTERVAL_SEC=10
LABEL=""
OUT_DIR="$DIAG_DIR"
ORIG_ARGS=("$@")

usage() {
  cat <<USAGE
Usage: sudo bash $0 [--interval-sec 10] [--label LABEL] [--out-dir DIR]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval-sec) INTERVAL_SEC="${2:-}"; shift 2 ;;
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
if ! [[ "$INTERVAL_SEC" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_SEC" -lt 1 ]]; then
  echo "--interval-sec must be a positive integer" >&2
  exit 1
fi

safe_label() { local value="$1"; value="${value//[^A-Za-z0-9_.-]/_}"; printf '%s' "$value"; }
mkdir -p "$OUT_DIR"
chmod 750 "$OUT_DIR" 2>/dev/null || true
STAMP="$(date +%Y%m%d_%H%M%S)"
LABEL_PART=""
[[ -n "$LABEL" ]] && LABEL_PART="_$(safe_label "$LABEL")"
OUT_FILE="${OUT_DIR}/live_stress_watch_${STAMP}${LABEL_PART}.txt"
[[ -e "$OUT_FILE" ]] && OUT_FILE="${OUT_DIR}/live_stress_watch_${STAMP}${LABEL_PART}_$RANDOM.txt"

metric_value() {
  local key="$1" default="$2"
  python3 - "$key" "$default" <<'PY' 2>/dev/null
import json, sys, urllib.request
key, default = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/admin/metrics_snapshot", timeout=2) as r:
        data = json.loads(r.read().decode())
    print(data.get(key, default))
except Exception:
    print(default)
PY
}

count_nginx_ws_101() {
  [[ -r /var/log/nginx/access.log ]] || { echo 0; return; }
  tail -n 5000 /var/log/nginx/access.log | awk '/\/ws\/listener/ && / 101 / {c++} END{print c+0}'
}

count_backend_pattern() {
  local pattern="$1"
  shopt -s nullglob
  local files=(/opt/byod/backend_data/events_log_*.jsonl /opt/byod/backend_data/connections_log_*.jsonl)
  shopt -u nullglob
  [[ ${#files[@]} -gt 0 ]] || { echo 0; return; }
  tail -n 5000 "${files[@]}" 2>/dev/null | grep -c "$pattern" || true
}

count_livekit_pattern() {
  local pattern="$1"
  journalctl -u byod-livekit --since "10 minutes ago" --no-pager 2>/dev/null | grep -Eic "$pattern" || true
}

cpu_line() {
  awk '/^cpu / {idle=$5; total=0; for (i=2;i<=NF;i++) total+=$i; print total, idle}' /proc/stat
}

net_total() {
  awk -F'[: ]+' 'NR>2 && $1 != "lo" {rx+=$3; tx+=$11} END{print rx+0, tx+0}' /proc/net/dev
}

read prev_cpu_total prev_cpu_idle < <(cpu_line)
read prev_rx prev_tx < <(net_total)
prev_time=$(date +%s)
prev_ws=$(count_nginx_ws_101)
prev_reconnect=$(count_backend_pattern RECONNECT_TOO_FAST)
prev_rate=$(count_backend_pattern CONNECTION_RATE_LIMIT)
prev_overflow=$(count_backend_pattern LISTENER_OVERFLOW)
prev_udp=$(count_livekit_pattern 'transport.*udp|udp')
prev_tcp=$(count_livekit_pattern 'transport.*tcp|tcp')
prev_unknown=$(count_livekit_pattern 'transport.*unknown|unknown')
prev_dtls=$(count_livekit_pattern 'dtls timeout')
prev_datachannel=$(count_livekit_pattern 'error reading data channel')
prev_signal=$(count_livekit_pattern 'SIGNAL_SOURCE_CLOSE')
prev_leave=$(count_livekit_pattern 'CLIENT_REQUEST_LEAVE')

{
  echo "timestamp_local=$(date -Is)"
  echo "timestamp_utc=$(date -u -Is)"
  printf 'command_line=%q' "$0"; printf ' %q' "${ORIG_ARGS[@]}"; printf '\n'
  echo "output_file=$OUT_FILE"
  echo "interval_sec=$INTERVAL_SEC"
  echo
} | tee -a "$OUT_FILE"

echo "Live stress watch writing: $OUT_FILE"
while true; do
  sleep "$INTERVAL_SEC"
  now=$(date +%s)
  read cpu_total cpu_idle < <(cpu_line)
  read rx tx < <(net_total)
  elapsed=$(( now - prev_time ))
  [[ $elapsed -lt 1 ]] && elapsed=1
  cpu_pct=$(awk -v pt="$prev_cpu_total" -v pi="$prev_cpu_idle" -v ct="$cpu_total" -v ci="$cpu_idle" 'BEGIN{dt=ct-pt; di=ci-pi; if(dt<=0){print "0.0"}else{printf "%.1f", (1-di/dt)*100}}')
  ram_pct=$(awk '/MemTotal:/ {t=$2} /MemAvailable:/ {a=$2} END{if(t>0) printf "%.1f", (1-a/t)*100; else print "0.0"}' /proc/meminfo)
  rx_mbps=$(awk -v a="$prev_rx" -v b="$rx" -v e="$elapsed" 'BEGIN{printf "%.2f", (b-a)*8/e/1000000}')
  tx_mbps=$(awk -v a="$prev_tx" -v b="$tx" -v e="$elapsed" 'BEGIN{printf "%.2f", (b-a)*8/e/1000000}')

  listeners=$(metric_value backend_listeners_count unknown)
  active_play=$(metric_value backend_active_play_count unknown)
  lk_listeners=$(metric_value livekit_listener_participants_count unknown)

  ws=$(count_nginx_ws_101)
  reconnect=$(count_backend_pattern RECONNECT_TOO_FAST)
  rate=$(count_backend_pattern CONNECTION_RATE_LIMIT)
  overflow=$(count_backend_pattern LISTENER_OVERFLOW)
  udp=$(count_livekit_pattern 'transport.*udp|udp')
  tcp=$(count_livekit_pattern 'transport.*tcp|tcp')
  unknown=$(count_livekit_pattern 'transport.*unknown|unknown')
  dtls=$(count_livekit_pattern 'dtls timeout')
  datachannel=$(count_livekit_pattern 'error reading data channel')
  signal=$(count_livekit_pattern 'SIGNAL_SOURCE_CLOSE')
  leave=$(count_livekit_pattern 'CLIENT_REQUEST_LEAVE')

  line="$(date -Is) backend_listeners=${listeners} active_play=${active_play} lk_listener_participants=${lk_listeners} cpu=${cpu_pct}% ram=${ram_pct}% rx=${rx_mbps}Mbps tx=${tx_mbps}Mbps nginx_ws_101_delta=$((ws-prev_ws)) rejects_delta=reconnect_too_fast:$((reconnect-prev_reconnect)),connection_rate_limit:$((rate-prev_rate)),listener_overflow:$((overflow-prev_overflow)) lk_transport_delta=udp:$((udp-prev_udp)),tcp:$((tcp-prev_tcp)),unknown:$((unknown-prev_unknown)) lk_warn_delta=dtls_timeout:$((dtls-prev_dtls)),data_channel:$((datachannel-prev_datachannel)),signal_close:$((signal-prev_signal)),client_leave:$((leave-prev_leave))"
  echo "$line" | tee -a "$OUT_FILE"

  prev_cpu_total=$cpu_total; prev_cpu_idle=$cpu_idle; prev_rx=$rx; prev_tx=$tx; prev_time=$now
  prev_ws=$ws; prev_reconnect=$reconnect; prev_rate=$rate; prev_overflow=$overflow
  prev_udp=$udp; prev_tcp=$tcp; prev_unknown=$unknown; prev_dtls=$dtls; prev_datachannel=$datachannel; prev_signal=$signal; prev_leave=$leave
done
