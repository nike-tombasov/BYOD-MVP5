# BYOD VPS Deploy Guide

This is the administrator workflow for a single BYOD VPS. The normal deploy path is: upload files with WinSCP, then paste one command in PuTTY. No manual `nano` editing is required during a clean deploy.

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
BYOD_ROOM_INPUT_PATH="/tmp/room_input.json"
BYOD_LIVEKIT_TGZ_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz"
BYOD_LIVEKIT_SHA256_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256"
BYOD_LISTENER_VENDOR_PATH="/tmp/livekit-client.umd.1.15.13.js"
```

Full schema and generated config mappings are in `configuration_reference.md`.

## One-command deploy

Paste this command in PuTTY after the files are uploaded:

```bash
sudo BYOD_VPS_CONFIG=/tmp/vps_config.env bash -c 'set -euo pipefail; test -r "$BYOD_VPS_CONFIG"; sed -i "s/\r$//" "$BYOD_VPS_CONFIG"; set -a; source "$BYOD_VPS_CONFIG"; set +a; apt-get update; apt-get install -y git curl ca-certificates; rm -rf /opt/byod/app-src; mkdir -p /opt/byod; git clone --branch "$BYOD_REPO_BRANCH" "$BYOD_REPO_URL" /opt/byod/app-src; bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/01_one_deploy_from_vps_config.sh "$BYOD_VPS_CONFIG"'
```

## What the command does

1. Verifies and loads `/tmp/vps_config.env`, converting CRLF to LF first.
2. Installs the minimal bootstrap packages: `git`, `curl`, `ca-certificates`.
3. Clones the configured branch into `/opt/byod/app-src`.
4. Runs `01_one_deploy_from_vps_config.sh` as the repository orchestrator.
5. Prepares the host, copies LiveKit release files to `/opt/byod/releases`, and verifies SHA-256 before installation.
6. Installs LiveKit, backend, Listener, and optional browser vendor file.
7. Generates `/opt/byod/config/backend.env` and `/opt/byod/config/livekit.yaml` from `/tmp/vps_config.env`.
8. Starts services, optionally imports `/tmp/room_input.json` through the backend validation endpoint, optionally applies the backend stress profile when `BYOD_ENABLE_BACKEND_STRESS_TEST=true`, and runs smoke test. The default is `false`, so normal deploys do not create or apply a stress drop-in.
9. Prints a colored summary with service health, URLs, smoke output path, and firewall reminder.

## Provider firewall

Allow inbound:

- `80/tcp`
- `7880/tcp`
- `7881/tcp`
- `50000-59999/udp`

Do **not** expose `8000/tcp`. Backend admin endpoints are local-only and are not proxied by nginx.

## Public client checks

- Listener URL: `http://<VPS_PUBLIC_IP>/`
- Backend health through nginx: `http://<VPS_PUBLIC_IP>/health`
- LiveKit URL given to browser clients: `ws://<VPS_PUBLIC_IP>:7880`

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

## Troubleshooting entry points

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label troubleshoot
sudo journalctl -u byod-backend -u byod-livekit -u nginx --no-pager -n 200
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh
```

Deep diagnostics, metrics, load checks, logs, and dangerous commands are documented in `testing_diagnostics_metrics.md`.

## Manifest

Deployment package manifest: `deploy/stage_x_ubuntu_pilot/manifest.yaml`.
