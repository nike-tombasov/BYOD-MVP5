# BYOD VPS Deploy Guide

This is the administrator workflow for a single BYOD VPS. First upload the files from Windows with `scp` (or WinSCP), then connect to the VPS with PuTTY or normal `ssh`, and paste the bash block below into the **remote VPS shell**. No manual `nano` editing is required during a clean deploy.

## Target environment

- Ubuntu Server 22.04 LTS or compatible systemd-based Ubuntu VPS.
- Public IPv4 address.
- Operator access through WinSCP for file upload and PuTTY for the shell command.
- Backend listens only on `127.0.0.1:8000`; nginx exposes only the public web and WebSocket paths.

## Files to upload to `/tmp` before deploy

Required for clean deploy:

```text
/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz
/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256
/tmp/vps_config.env
```

Optional fallback files:

```text
/tmp/livekit-client.umd.1.15.13.js
/tmp/room_input.json
```

If `room_input.json` is missing, deploy continues with the persisted/default room config and prints a warning. If the file exists and backend validation rejects it, deploy fails. If the Listener vendor file is missing, deploy continues with CDN fallback and prints a warning.

## `/tmp/vps_config.env`

Create a shell-compatible dotenv file and upload it to `/tmp/vps_config.env`. Recommended permissions after upload:

```bash
sudo chmod 600 /tmp/vps_config.env
```

Minimal sample:

```bash
BYOD_REPO_URL="https://github.com/nike-tombasov/BYOD-MVP5.git"
BYOD_REPO_BRANCH="codex-qv5tz8"
BYOD_VPS_PUBLIC_IP="203.0.113.10"
BYOD_PUBLIC_ORIGIN="http://203.0.113.10"
BYOD_LIVEKIT_URL="ws://203.0.113.10:7880"
BYOD_LIVEKIT_API_KEY="replace_with_livekit_key"
BYOD_LIVEKIT_API_SECRET="replace_with_long_livekit_secret"
BYOD_BACKEND_HOST="127.0.0.1"
BYOD_BACKEND_PORT="8000"
BYOD_DEFAULT_PIN="123456"
BYOD_ENABLE_BACKEND_STRESS_TEST=false
BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS=2
BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE=""
BYOD_ROOM_INPUT_PATH="/tmp/room_input.json"
BYOD_LIVEKIT_TGZ_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz"
BYOD_LIVEKIT_SHA256_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256"
BYOD_LISTENER_VENDOR_PATH="/tmp/livekit-client.umd.1.15.13.js"
```

Full schema and generated config mappings are in `configuration_reference.md`. For normal deploy, keep `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` empty. After VPS sizing/stress testing, it can be set in `/opt/byod/config/backend.env` and applied with `sudo systemctl restart byod-backend`.

For domain mode, first create external A-records for `listen-*` (guest Listener), `lk-*` (LiveKit SDK signaling), and optionally `admin-*` (reserved only), all pointing to this VPS. Use the domain sample in `configuration_reference.md` and set `BYOD_DOMAIN_TLS_MODE=true`. Deployment checks DNS before certificate issuance, obtains a trusted certificate with certbot, validates nginx, and enables HTTPS/WSS. Direct-IP mode remains the default and requires none of these values.

Stage XII does not implement an Admin UI and public backend `/admin/*` is blocked. The Publisher UI has no dedicated domain: its operator uses a manually configured URL such as `ws://194.58.118.140/ws/publisher` through nginx. Do not create a Publisher DNS record. Event aliases are paths beneath the Listener URL, not DNS records.

## Launch deploy from the VPS shell

After uploading all files, connect to the VPS with PuTTY or `ssh` and paste this entire bash block into the remote Linux shell. Do **not** paste PowerShell here-strings (`@' ... '@`) into Linux bash. If using PowerShell on the local Windows PC, use it only for the documented `scp` upload commands and a normal `ssh root@<VPS_IP>` login; paste and run the deploy block only after that login, at the remote Linux prompt.

```bash
cat >/tmp/byod_run_deploy.sh <<'BYOD_DEPLOY'
#!/usr/bin/env bash
set -euo pipefail

BYOD_VPS_CONFIG=/tmp/vps_config.env

test -r "$BYOD_VPS_CONFIG"
sed -i 's/\r$//' "$BYOD_VPS_CONFIG"

set -a
source "$BYOD_VPS_CONFIG"
set +a

printf 'BYOD_REPO_URL=[%s]\n' "$BYOD_REPO_URL"
printf 'BYOD_REPO_BRANCH=[%s]\n' "$BYOD_REPO_BRANCH"

apt-get update
apt-get install -y git curl ca-certificates tar gzip

cat >/tmp/byod_fetch_app_source.sh <<'BYOD_FETCH'
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <github-repo-url> <branch> <destination>" >&2
  exit 2
fi

REPO_URL=$1
REF=$2
DEST=$3

rm -rf "$DEST"
mkdir -p "$DEST"

if GIT_TERMINAL_PROMPT=0 git clone --branch "$REF" --single-branch "$REPO_URL" "$DEST"; then
  echo "OK: fetched app source with git clone into $DEST"
  exit 0
fi

echo "WARNING: git clone failed; trying the public GitHub codeload archive fallback." >&2

if [[ ! "$REPO_URL" =~ ^https://github\.com/([^/]+)/([^/]+)$ ]]; then
  echo "FATAL: archive fallback supports only https://github.com/<owner>/<repo>.git URLs." >&2
  exit 1
fi

OWNER=${BASH_REMATCH[1]}
REPO=${BASH_REMATCH[2]}
REPO=${REPO%.git}
if [[ -z "$OWNER" || -z "$REPO" ]]; then
  echo "FATAL: could not derive a GitHub owner and repository from $REPO_URL" >&2
  exit 1
fi

# Git branch names may contain slashes; encode them so they remain one URL path value.
ENCODED_REF=${REF//\//%2F}
ARCHIVE_URL="https://codeload.github.com/$OWNER/$REPO/tar.gz/refs/heads/$ENCODED_REF"
ARCHIVE_PATH=$(mktemp /tmp/byod-app-source.XXXXXX.tar.gz)
trap 'rm -f "$ARCHIVE_PATH"' EXIT

rm -rf "$DEST"
mkdir -p "$DEST"
if ! curl -fL --retry 3 --retry-delay 2 "$ARCHIVE_URL" -o "$ARCHIVE_PATH"; then
  echo "FATAL: GitHub archive download failed after git clone also failed." >&2
  exit 1
fi
tar -xzf "$ARCHIVE_PATH" --strip-components=1 -C "$DEST"

if ! test -f "$DEST/deploy/stage_x_ubuntu_pilot/scripts/01_one_deploy_from_vps_config.sh"; then
  echo "FATAL: downloaded archive does not contain the expected Stage XII deploy script." >&2
  exit 1
fi

echo "OK: fetched app source from the GitHub codeload archive into $DEST"
BYOD_FETCH
chmod 700 /tmp/byod_fetch_app_source.sh
bash /tmp/byod_fetch_app_source.sh "$BYOD_REPO_URL" "$BYOD_REPO_BRANCH" /opt/byod/app-src

bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/01_one_deploy_from_vps_config.sh "$BYOD_VPS_CONFIG"
BYOD_DEPLOY

bash /tmp/byod_run_deploy.sh
```

The temporary bootstrap helper mirrors the checked-in `deploy/stage_x_ubuntu_pilot/scripts/02_fetch_app_source.sh`; future wrappers can call that checked-in helper whenever a source tree is already available.

## What the command does

1. Verifies and loads `/tmp/vps_config.env`, converting CRLF to LF first.
2. Installs bootstrap packages and fetches the configured branch into `/opt/byod/app-src`, falling back from `git clone` to a public GitHub codeload archive when necessary.
3. Prepares the host and verifies/copies the LiveKit release artifact.
4. Installs LiveKit, backend, and Listener.
5. Generates `/opt/byod/config/backend.env` and `/opt/byod/config/livekit.yaml`.
6. Installs the optional browser vendor file and enables/starts services.
7. Imports `/tmp/room_input.json` through backend validation when present. With no input, it clears any persisted alias, restarts backend, and waits for health.
8. In domain mode, runs DNS preflight and certbot/nginx setup using the validated/persisted `subsite_name`.
9. Applies the optional stress profile, then runs smoke after domain nginx has been rendered.
10. Prints service health, canonical client URLs, smoke output path, and firewall reminders.

## Provider firewall

Allow inbound:

- `80/tcp`
- `443/tcp` in domain mode
- `7880/tcp` in direct-IP mode
- `7881/tcp`
- `50000-59999/udp`

Do **not** expose `8000/tcp`. Backend admin endpoints are local-only and are not proxied by nginx.

## Public client checks

Direct-IP mode:
- Listener: `http://<VPS_PUBLIC_IP>/`;
- health: `http://<VPS_PUBLIC_IP>/health`;
- LiveKit signaling: `ws://<VPS_PUBLIC_IP>:7880`;
- Publisher `Server IP`: `ws://<VPS_PUBLIC_IP>/ws/publisher`.

Domain mode:
- Listener root: `https://<BYOD_LISTENER_DOMAIN>/`;
- health: `https://<BYOD_LISTENER_DOMAIN>/health`;
- direct-IP fallback: `http://<VPS_PUBLIC_IP>/`;
- configured alias, if present: `https://<BYOD_LISTENER_DOMAIN>/<subsite_name>/` and its direct-IP equivalent;
- Publisher `Server IP`: `ws://<VPS_PUBLIC_IP>/ws/publisher`.

A wrong or old Listener alias must return `404`. Root remains valid whether or not an alias is configured.

## Manual room config import

Use this only as a fallback/maintenance procedure after deploy. The one-command deploy already imports `/tmp/room_input.json` when it exists.

```bash
sudo curl -sf -F "file=@/tmp/room_input.json;type=application/json" http://127.0.0.1:8000/admin/import_json | python3 -m json.tool
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label manual_room_import
```

A successful response contains `"ok": true` and an `applied` summary. A validation failure returns `"ok": false` with errors.

## Manual LiveKit browser client vendor install

Use this only if the vendor file was uploaded after deploy or if the Listener directory was refreshed:

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/66_install_livekit_vendor_from_tmp.sh /tmp/livekit-client.umd.1.15.13.js
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label manual_vendor_install
```

## Backend runtime commands without restart

Runtime commands are executed through a local-only backend endpoint. nginx does not expose `/admin/*` publicly.

Examples:

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh status
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh "set_room_status OPENED"
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh "set_listen channel_1 true"
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh "set_channel_label channel_1 Russian - RUS - Русский"
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh "off_air channel_1"
```

Supported commands: `help`, `status`, `set_room_status <OPENED|BLOCKED|CLOSED>`, `start_recording`, `stop_recording`, `set_channel_label <channel_id> <new_label>`, `set_listen <channel_id> <true|false>`, `off_air <channel_id>`.

## `REMOTE HOST IDENTIFICATION HAS CHANGED` after VPS rebuild

This warning is expected when the VPS was intentionally rebuilt or reinstalled and therefore received a new SSH host key. If the VPS was **not** intentionally rebuilt, stop: the warning can indicate a real man-in-the-middle attack.

If and only if the VPS was intentionally recreated and its IP is correct, remove the old key on the Windows PC, then reconnect:

```powershell
ssh-keygen -R 194.58.118.140
# For another server:
ssh-keygen -R <VPS_IP>
ssh root@194.58.118.140
```

Check and accept the new fingerprint only when the IP and rebuild are trusted. As a manual fallback, open `C:\Users\<WindowsUser>\.ssh\known_hosts`, remove the offending line reported by SSH (for example, line `3`), and reconnect. Do not disable SSH host-key checking globally.

## Troubleshooting entry points

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label troubleshoot
sudo journalctl -u byod-backend -u byod-livekit -u nginx --no-pager -n 200
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh
```

Deep diagnostics, metrics, load checks, logs, and dangerous commands are documented in `testing_diagnostics_metrics.md`.

## Manifest

Deployment package manifest: `deploy/stage_x_ubuntu_pilot/manifest.yaml`.

## Publisher `Server IP` and event path rules

The Publisher UI is unchanged and its field remains labelled `Server IP`, but it requires a **full backend WebSocket URL**. In VPS/domain mode enter `ws://<VPS_PUBLIC_IP>/ws/publisher`; for hall 1 this is `ws://194.58.118.140/ws/publisher`. Do not enter `194.58.118.140`, `ws://194.58.118.140:8000/ws/publisher`, `https://listen-1.k-pls.ru/`, or `wss://lk-1.k-pls.ru`.

For same-PC development use `ws://127.0.0.1:8000/ws/publisher`. For LAN testing only, when the backend is intentionally bound to LAN, use `ws://<LAN_BACKEND_IP>:8000/ws/publisher`. Publisher has no dedicated DNS name; do not create one. Port 8000 stays private on a VPS, and nginx exposes only `/ws/publisher`.

Optional room-config `subsite_name` is one current-event Listener path slug (for example `test-conf` gives `/test-conf/`). Root remains valid. Missing/empty means no alias, and wrong or old paths return `404`. It does not create DNS or multi-room routing.
