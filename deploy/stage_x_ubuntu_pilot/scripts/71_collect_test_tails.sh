#!/usr/bin/env bash
set -u
SINCE="10 minutes ago"
if [[ "${1:-}" == "--since" && -n "${2:-}" ]]; then
  SINCE="$2"
elif [[ -n "${1:-}" ]]; then
  SINCE="$1"
fi

collect_journal() {
  local unit="$1"
  local out="$2"
  local since="$3"
  if ! journalctl -u "$unit" --since "$since" --no-pager | tee "$out"; then
    printf 'WARNING: failed to collect %s journal since %s\n' "$unit" "$since" | tee "$out"
  fi
  if [[ ! -s "$out" ]]; then
    printf 'WARNING: %s was empty for %s; retrying 30 minutes ago\n' "$out" "$since" | tee "$out"
    journalctl -u "$unit" --since "30 minutes ago" --no-pager | tee -a "$out" || true
  fi
  if [[ ! -s "$out" ]]; then
    printf 'WARNING: %s is still empty; no journal rows available or insufficient permissions\n' "$out" | tee "$out"
  fi
}

collect_file_tail() {
  local path="$1"
  local out="$2"
  if [[ -r "$path" ]]; then
    tail -n 500 "$path" | tee "$out"
  else
    printf 'WARNING: %s is missing or unreadable\n' "$path" | tee "$out"
  fi
}

collect_journal byod-backend backend_tail.txt "$SINCE"
collect_journal byod-livekit livekit_tail.txt "$SINCE"
collect_file_tail /var/log/nginx/access.log nginx_access_tail.txt
collect_file_tail /var/log/nginx/error.log nginx_error_tail.txt

{
  date -Is
  echo '--- ss port 80 ---'
  ss -tan '( sport = :80 or dport = :80 )' || true
  echo '--- time-wait count ---'
  ss -tan state time-wait | wc -l || true
  echo '--- established count ---'
  ss -tan state established | wc -l || true
  echo '--- limits ---'
  systemctl show nginx -p LimitNOFILE || true
  systemctl show byod-backend -p LimitNOFILE || true
} | tee system_limits_snapshot.txt
