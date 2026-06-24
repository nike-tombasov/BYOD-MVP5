#!/usr/bin/env bash
set -euo pipefail

DIAG_DIR="/opt/byod/diagnostics"
ENDPOINT="http://127.0.0.1:8000/admin/metrics_snapshot"
LABEL=""
OUT_DIR="$DIAG_DIR"

usage() {
  cat <<USAGE
Usage: sudo bash $0 [--label LABEL] [--out-dir DIR]

Captures local-only backend metrics snapshot from ${ENDPOINT}.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label)
      LABEL="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run on the VPS as root: sudo bash $0" >&2
  exit 1
fi

safe_label() {
  local value="$1"
  value="${value//[^A-Za-z0-9_.-]/_}"
  printf '%s' "$value"
}

make_path() {
  local base="$1" ext="$2" label_part="" candidate
  [[ -n "$LABEL" ]] && label_part="_$(safe_label "$LABEL")"
  candidate="${OUT_DIR}/${base}_${STAMP}${label_part}.${ext}"
  if [[ -e "$candidate" ]]; then
    candidate="${OUT_DIR}/${base}_${STAMP}${label_part}_$RANDOM.${ext}"
  fi
  printf '%s' "$candidate"
}

mkdir -p "$OUT_DIR"
chmod 750 "$OUT_DIR" 2>/dev/null || true
STAMP="$(date +%Y%m%d_%H%M%S)"
JSON_OUT="$(make_path metrics_snapshot json)"
TXT_OUT="$(make_path metrics_snapshot txt)"
TMP_RAW="$(mktemp)"
trap 'rm -f "$TMP_RAW"' EXIT

if ! curl -fsS --max-time 10 "$ENDPOINT" -o "$TMP_RAW"; then
  {
    echo "timestamp_local=$(date -Is)"
    echo "timestamp_utc=$(date -u -Is)"
    echo "endpoint=${ENDPOINT}"
    echo "ERROR: metrics snapshot unavailable from local-only backend endpoint"
  } >"$TXT_OUT"
  printf '{\n  "error": "metrics snapshot unavailable",\n  "endpoint": "%s"\n}\n' "$ENDPOINT" >"$JSON_OUT"
  echo "Metrics snapshot unavailable; wrote warning files:"
  echo "  $JSON_OUT"
  echo "  $TXT_OUT"
  exit 1
fi

if command -v jq >/dev/null 2>&1; then
  jq . "$TMP_RAW" >"$JSON_OUT"
else
  python3 -m json.tool "$TMP_RAW" >"$JSON_OUT"
fi

python3 - "$JSON_OUT" "$TXT_OUT" "$ENDPOINT" <<'PY'
import json
import sys
from datetime import datetime, timezone

json_path, txt_path, endpoint = sys.argv[1:4]
try:
    data = json.load(open(json_path, encoding="utf-8"))
except Exception as exc:
    data = {"_parse_error": str(exc)}

def pick(*names, default="unknown"):
    for name in names:
        cur = data
        ok = True
        for part in name.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            return cur
    return default

rows = [
    ("timestamp_local", datetime.now().astimezone().isoformat(timespec="seconds")),
    ("timestamp_utc", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    ("endpoint", endpoint),
    ("backend_publishers_count", pick("backend_publishers_count", "publishers_count", "publishers", default=0)),
    ("backend_listeners_count", pick("backend_listeners_count", "listeners_count", "listeners", default=0)),
    ("backend_active_play_count", pick("backend_active_play_count", "active_play_count", "active_plays", default=0)),
    ("livekit_api_ok", pick("livekit_api_ok", default=False)),
    ("livekit_rooms_count", pick("livekit_rooms_count", "rooms_count", default=0)),
    ("livekit_participants_count", pick("livekit_participants_count", "participants_count", default=0)),
    ("livekit_listener_participants_count", pick("livekit_listener_participants_count", default=0)),
    ("livekit_publisher_participants_count", pick("livekit_publisher_participants_count", default=0)),
    ("max_active_listeners", pick("max_active_listeners")),
    ("max_new_connections_per_sec", pick("max_new_connections_per_sec")),
    ("loadgen_reconnect_bypass_enabled", pick("loadgen_reconnect_bypass_enabled")),
    ("listener_min_reconnect_interval_per_ip_seconds", pick("listener_min_reconnect_interval_per_ip_seconds")),
]
with open(txt_path, "w", encoding="utf-8") as fh:
    fh.write("BYOD metrics snapshot summary\n")
    for key, value in rows:
        fh.write(f"{key}: {value}\n")
PY

echo "Metrics snapshot files:"
echo "  $JSON_OUT"
echo "  $TXT_OUT"
