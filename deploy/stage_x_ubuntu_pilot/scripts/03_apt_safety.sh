#!/usr/bin/env bash
# Apt safety functions for the short-lived Stage XII event appliance.
# This file is intentionally sourceable; do not enable shell options here.

_BYOD_APT_UNITS=(
  apt-daily.timer
  apt-daily-upgrade.timer
  apt-daily.service
  apt-daily-upgrade.service
  unattended-upgrades.service
)
_BYOD_APT_LOCKS=(
  /var/lib/dpkg/lock
  /var/lib/dpkg/lock-frontend
  /var/lib/apt/lists/lock
  /var/cache/apt/archives/lock
)

_byod_lock_holders() {
  local lock=$1
  if command -v fuser >/dev/null 2>&1; then
    fuser "$lock" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -t -- "$lock" 2>/dev/null || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$lock" <<'PY'
import fcntl, os, sys
try:
    fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o640)
    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.lockf(fd, fcntl.LOCK_UN)
    os.close(fd)
except (PermissionError, BlockingIOError):
    print("held")
PY
  else
    # A normal audit is a safe last-resort probe: unlike deleting lock files it
    # asks dpkg to open its database in the supported way.
    dpkg --audit >/dev/null 2>&1 || printf 'held\n'
  fi
}

disable_event_vps_auto_updates() {
  export DEBIAN_FRONTEND=noninteractive

  if command -v systemctl >/dev/null 2>&1; then
    systemctl stop "${_BYOD_APT_UNITS[@]}" >/dev/null 2>&1 || true
    systemctl disable "${_BYOD_APT_UNITS[@]}" >/dev/null 2>&1 || true
    systemctl mask "${_BYOD_APT_UNITS[@]}" >/dev/null 2>&1 || true
  else
    printf 'WARNING: systemctl is unavailable; apt units could not be stopped or masked.\n' >&2
  fi

  mkdir -p /etc/apt/apt.conf.d
  cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
APT::Periodic::AutocleanInterval "0";
EOF
  if [[ -e /etc/apt/apt.conf.d/10periodic ]]; then
    cat >/etc/apt/apt.conf.d/10periodic <<'EOF'
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
APT::Periodic::AutocleanInterval "0";
EOF
  fi
  cat >/etc/apt/apt.conf.d/99byod-no-auto-reboot <<'EOF'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
EOF

  # Unit stop above gives first-boot unattended work a short, clean grace
  # period. Never remove lock files and never terminate an operator's apt.
  local deadline=$((SECONDS + 15)) lock holders
  while (( SECONDS < deadline )); do
    holders=''
    for lock in "${_BYOD_APT_LOCKS[@]}"; do
      [[ -e $lock ]] || continue
      holders=$(_byod_lock_holders "$lock")
      [[ -z $holders ]] || break
    done
    [[ -n $holders ]] || break
    sleep 1
  done
  if [[ -n ${holders:-} ]]; then
    printf 'WARNING: apt/dpkg remains busy after stopping automatic update units; the package lock wait will continue safely.\n' >&2
  fi
  printf 'OK: automatic apt updates and automatic reboots are disabled for this event VPS.\n'
}

wait_for_apt_locks() {
  local timeout=${1:-180}
  [[ $timeout =~ ^[0-9]+$ ]] || { printf 'FATAL: apt lock timeout must be seconds.\n' >&2; return 2; }
  local deadline=$((SECONDS + timeout)) lock holders holder_info details
  while :; do
    details=''
    for lock in "${_BYOD_APT_LOCKS[@]}"; do
      [[ -e $lock ]] || continue
      holders=$(_byod_lock_holders "$lock")
      if [[ -n $holders ]]; then
        holder_info=$holders
        if [[ $holders =~ ^[[:space:][:digit:]]+$ ]] && command -v ps >/dev/null 2>&1; then
          holder_info=$(ps -o pid=,comm=,args= -p "$(tr ' ' ',' <<<"$holders" | sed 's/^,*//;s/,*$//')" 2>/dev/null || printf '%s' "$holders")
        fi
        details="$lock (holder: $holder_info)"
        break
      fi
    done
    if [[ -z $details ]]; then
      printf 'OK: apt/dpkg package locks are available.\n'
      return 0
    fi
    if (( SECONDS >= deadline )); then
      printf 'FATAL: apt/dpkg is still busy after %s seconds: %s. Lock files were not removed; inspect the holder before retrying.\n' "$timeout" "$details" >&2
      return 1
    fi
    printf 'WARNING: waiting for apt/dpkg lock: %s\n' "$details" >&2
    sleep 2
  done
}

apt_update_safe() {
  wait_for_apt_locks "${BYOD_APT_LOCK_TIMEOUT:-180}"
  DEBIAN_FRONTEND=noninteractive apt-get update
}

apt_install_safe() {
  wait_for_apt_locks "${BYOD_APT_LOCK_TIMEOUT:-180}"
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  [[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root: sudo bash $0" >&2; exit 1; }
  disable_event_vps_auto_updates
  wait_for_apt_locks
fi
