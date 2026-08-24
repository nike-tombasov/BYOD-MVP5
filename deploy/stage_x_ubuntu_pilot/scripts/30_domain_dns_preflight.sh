#!/usr/bin/env bash
set -euo pipefail

fatal() { printf 'DNS FAIL: %s\n' "$*" >&2; exit 1; }

case "${BYOD_DOMAIN_TLS_MODE:-false}" in
  true) ;;
  false) printf 'DNS SKIP: domain TLS mode is disabled\n'; exit 0 ;;
  *) fatal 'BYOD_DOMAIN_TLS_MODE must be true or false' ;;
esac

[[ -n "${BYOD_VPS_PUBLIC_IP:-}" ]] || fatal 'BYOD_VPS_PUBLIC_IP is required'
command -v getent >/dev/null 2>&1 || fatal 'getent is required for DNS preflight'

check_domain() {
  local domain="$1" addresses
  addresses="$(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | sort -u || true)"
  [[ -n "$addresses" ]] || fatal "$domain has no IPv4 DNS result"
  if ! grep -Fxq "$BYOD_VPS_PUBLIC_IP" <<<"$addresses"; then
    fatal "$domain resolves to $(tr '\n' ',' <<<"$addresses" | sed 's/,$//'), expected $BYOD_VPS_PUBLIC_IP"
  fi
  printf 'DNS PASS: %s -> %s\n' "$domain" "$BYOD_VPS_PUBLIC_IP"
}

check_domain "${BYOD_LISTENER_DOMAIN:?BYOD_LISTENER_DOMAIN is required}"
check_domain "${BYOD_LIVEKIT_DOMAIN:?BYOD_LIVEKIT_DOMAIN is required}"
[[ -z "${BYOD_ADMIN_DOMAIN:-}" ]] || check_domain "$BYOD_ADMIN_DOMAIN"
