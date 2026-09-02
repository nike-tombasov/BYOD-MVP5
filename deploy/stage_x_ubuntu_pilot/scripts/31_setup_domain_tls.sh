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
room_config=/opt/byod/backend_data/room_config_v1.json
subsite_name="$(python3 - "$room_config" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if path.is_file():
    value = json.loads(path.read_text(encoding="utf-8")).get("subsite_name")
    if isinstance(value, str):
        print(value)
PY
)"
export BYOD_NGINX_DOMAIN_NAMES="$domain_names" BYOD_NGINX_ADMIN_SERVER="$admin_server" BYOD_NGINX_SUBSITE_NAME="$subsite_name"
python3 - "$REPO_ROOT/deploy/stage_x_ubuntu_pilot/nginx/byod-domains.conf.template" <<'PY' > /etc/nginx/sites-available/byod-domains.conf
import os, pathlib, sys
template = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
alias = os.environ["BYOD_NGINX_SUBSITE_NAME"]
locations = ""
if alias:
    locations = f"location = /{alias} {{ return 308 /{alias}/; }}\n    location = /{alias}/ {{ try_files /index.html =404; add_header Cache-Control \"no-store\"; }}"
replacements = {
    "__DOMAIN_NAMES__": os.environ["BYOD_NGINX_DOMAIN_NAMES"],
    "__LISTENER_DOMAIN__": os.environ["BYOD_LISTENER_DOMAIN"],
    "__LIVEKIT_DOMAIN__": os.environ["BYOD_LIVEKIT_DOMAIN"],
    "__CERT_NAME__": os.environ["BYOD_LISTENER_DOMAIN"],
    "__ADMIN_SERVER__": os.environ["BYOD_NGINX_ADMIN_SERVER"],
    "__ALIAS_LOCATIONS__": locations,
}
for old, new in replacements.items():
    template = template.replace(old, new)
print(template, end="")
PY
ln -sfn /etc/nginx/sites-available/byod-domains.conf /etc/nginx/sites-enabled/byod-domains.conf
rm -f /etc/nginx/sites-enabled/byod-listener.conf
nginx -t || fatal 'generated domain nginx configuration is invalid'
systemctl reload nginx
printf 'TLS PASS: HTTPS/WSS configured for %s\n' "$domain_names"
