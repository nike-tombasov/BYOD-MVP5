#!/usr/bin/env bash
set -euo pipefail

fatal() { printf 'TLS FAIL: %s\n' "$*" >&2; exit 1; }
case "${BYOD_DOMAIN_TLS_MODE:-false}" in
  true) ;;
  false) printf 'TLS SKIP: domain TLS mode is disabled\n'; exit 0 ;;
  *) fatal 'BYOD_DOMAIN_TLS_MODE must be true or false' ;;
esac
[[ ${EUID} -eq 0 ]] || fatal 'run as root'

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/scripts/30_domain_dns_preflight.sh"

export DEBIAN_FRONTEND=noninteractive
if ! command -v certbot >/dev/null 2>&1 || ! dpkg-query -W python3-certbot-nginx >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot python3-certbot-nginx
fi

domains=("$BYOD_LISTENER_DOMAIN" "$BYOD_LIVEKIT_DOMAIN")
[[ -z "${BYOD_ADMIN_DOMAIN:-}" ]] || domains+=("$BYOD_ADMIN_DOMAIN")
cert_args=()
for domain in "${domains[@]}"; do cert_args+=(-d "$domain"); done

# One SAN certificate gives nginx a stable lineage name and makes repeated deploys renew-only.
certbot certonly --webroot -w /opt/byod/listener --non-interactive --agree-tos \
  --email "$BYOD_TLS_EMAIL" --cert-name "$BYOD_LISTENER_DOMAIN" --keep-until-expiring "${cert_args[@]}" \
  || fatal 'certificate issuance failed; verify DNS and inbound TCP ports 80/443'

install -m 0644 "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/byod-websocket-proxy.conf" /etc/nginx/byod-websocket-proxy.conf
domain_names="$BYOD_LISTENER_DOMAIN $BYOD_LIVEKIT_DOMAIN"
admin_server=''
if [[ -n "${BYOD_ADMIN_DOMAIN:-}" ]]; then
  domain_names+=" $BYOD_ADMIN_DOMAIN"
  admin_server="server { listen 443 ssl; server_name $BYOD_ADMIN_DOMAIN; ssl_certificate /etc/letsencrypt/live/$BYOD_LISTENER_DOMAIN/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/$BYOD_LISTENER_DOMAIN/privkey.pem; location / { return 404; } }"
fi
sed -e "s/__DOMAIN_NAMES__/$domain_names/g" \
    -e "s/__LISTENER_DOMAIN__/$BYOD_LISTENER_DOMAIN/g" \
    -e "s/__LIVEKIT_DOMAIN__/$BYOD_LIVEKIT_DOMAIN/g" \
    -e "s/__CERT_NAME__/$BYOD_LISTENER_DOMAIN/g" \
    -e "s|__ADMIN_SERVER__|$admin_server|g" \
    "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/byod-domains.conf.template" > /etc/nginx/sites-available/byod-domains.conf
ln -sfn /etc/nginx/sites-available/byod-domains.conf /etc/nginx/sites-enabled/byod-domains.conf
rm -f /etc/nginx/sites-enabled/byod-listener.conf
nginx -t || fatal 'generated domain nginx configuration is invalid'
systemctl reload nginx
printf 'TLS PASS: HTTPS/WSS configured for %s\n' "$domain_names"
