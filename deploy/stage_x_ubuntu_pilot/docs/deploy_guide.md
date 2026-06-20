# Stage X Ubuntu Pilot Deploy Guide

This guide is written specifically for:

Server:
- Ubuntu Server 22.04 LTS
- Clean VPS
- Public IPv4 address

Operator workstation:
- Windows 10/11
- PuTTY
- WinSCP

All commands in this document assume that environment.

Typical workflow for File Transfer Convention (WinSCP):

1. Upload file to /tmp using WinSCP.
2. Connect via PuTTY.
3. Move file using sudo mv.
4. Adjust ownership using sudo chown.

Do not assume command-line file-transfer tooling.

## 1) Bootstrap the clean VPS and clone branch MVP11

```bash
sudo apt-get update
sudo apt-get install -y git
sudo mkdir -p /opt/byod
sudo chown "$USER:$USER" /opt/byod
git clone --branch MVP11 https://github.com/nike-tombasov/BYOD-MVP5 /opt/byod/app-src
cd /opt/byod/app-src
sudo bash deploy/stage_x_ubuntu_pilot/scripts/00_prepare_host.sh
```

The prepare script installs the remaining host packages (including `btop` for operator monitoring, and ensuring `git` is present), creates the `byod` service account, and creates these directories:

- `/opt/byod/app`
- `/opt/byod/config`
- `/opt/byod/livekit`
- `/opt/byod/listener`
- `/opt/byod/backend_data`
- `/opt/byod/logs`
- `/opt/byod/releases`

## 2) Put LiveKit pinned artifact + checksum (preferred)

Expected files before install:

- `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz`
- `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`

Download the two files on the Windows operator workstation, then use WinSCP to
upload them. If checksum-generation tooling is available on the workstation,
generate the `.sha256` file there; otherwise obtain and verify the checksum
from the trusted release process before upload.

In WinSCP, upload both files to `/tmp` first; a regular SSH user cannot write
directly to the service-owned release directory after host preparation. Then
open PuTTY and run:

```bash
sudo mv /tmp/livekit-server-v1.9.11-linux-amd64.tar.gz* /opt/byod/releases/
sudo chown byod:byod /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz*
cd /opt/byod/app-src
```

Install LiveKit:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/10_install_livekit.sh
```

Fallback:
- If custom artifact is not present, script downloads from official GitHub release URL.

## 3) Install backend and listener

Before installing the Listener, verify that this pinned browser SDK file exists
in the repository checkout:

```text
src/listener/vendor/livekit-client.umd.1.15.13.js
```

If it is missing, put `livekit-client.umd.1.15.13.js` into
`src/listener/vendor` before deploy. The listener installer intentionally stops
with this instruction rather than deploying a Listener that depends on CDN
availability.

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/20_install_backend.sh
sudo bash deploy/stage_x_ubuntu_pilot/scripts/30_install_listener.sh
```

Notes:
- Backend installs **backend-only** Python requirements.
- `/opt/byod/config/livekit.yaml` is auto-created from template if missing (existing file is not overwritten).

## 4) Configure pilot values

Edit backend env file:

```bash
sudo nano /opt/byod/config/backend.env
```

For today's public-IP/HTTP pilot, set:

- `BYOD_LIVEKIT_URL=ws://<VPS_PUBLIC_IP>:7880`
- `BYOD_LIVEKIT_API_KEY=<pilot_key>`
- `BYOD_LIVEKIT_API_SECRET=<pilot_secret>`
- `BYOD_CORS_ALLOWED_ORIGIN=http://<VPS_PUBLIC_IP>`

Emergency/stress numeric backend limits, including clean-deploy
`target_capacity`, are grouped in the top operator block of
`src/backend/config.py`. Edit only the number on the right side, then restart
`byod-backend`.

Edit LiveKit config:

```bash
sudo nano /opt/byod/config/livekit.yaml
```

Replace API key/secret values in `keys:`. The key and secret must exactly match
`BYOD_LIVEKIT_API_KEY` and `BYOD_LIVEKIT_API_SECRET` in `backend.env`.

Use quotes around both values in the LiveKit YAML:

```yaml
keys:
  "testvps": "secret-value"
```

The API key and API secret in `/opt/byod/config/backend.env` and
`/opt/byod/config/livekit.yaml` must match exactly, including case and any
punctuation.

If either file was edited or transferred from Windows, remove CRLF line endings:

```bash
sudo sed -i 's/\r$//' /opt/byod/config/backend.env
sudo sed -i 's/\r$//' /opt/byod/config/livekit.yaml
```

## 5) Enable services and nginx

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/40_enable_services.sh
```

This installs the full BYOD `/etc/nginx/nginx.conf` template, keeps `byod-listener.conf` as the site config, backs up the previous nginx main config before replacement, validates with `nginx -t`, and installs service file descriptor limits: nginx override `LimitNOFILE=200000` and backend `LimitNOFILE=200000`.

## 6) Configure the provider firewall

The VPS provider firewall must allow inbound `80/tcp`, `7880/tcp`, `7881/tcp`,
and `50000-50100/udp`. Port `8000/tcp` stays private because the backend binds
to `127.0.0.1` and nginx proxies backend HTTP and WebSocket traffic.

Configure these rules before attempting the final browser and Publisher tests.

## 7) Run smoke and client tests

Run the automated smoke test on the VPS:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh
```

Expected output is concise one-line service status, for example: `backend: active, health=ok, port=8000-listening`, `nginx: active, config=ok, worker_connections=65535, nofile=200000`, `livekit: active, port=7880-listening, tcp=7881-listening`, plus `btop`, vendor, and local metrics checks.

Then perform the public client checks:

1. Open `http://<VPS_PUBLIC_IP>/` in a browser and confirm the listener
   connects.
2. Start Publisher and manually replace its default localhost backend value
   with `ws://<VPS_PUBLIC_IP>/ws/publisher` before connecting. The Publisher's
   localhost backend default is only suitable when the backend runs on the
   same machine, not for VPS testing.

The IP/HTTP setup is acceptable only for this pilot. A production or
domain-based deployment should add TLS and use HTTPS/WSS.

## 8) Connection troubleshooting and diagnostic collection

Use these exact client URLs for the public-IP/HTTP pilot:

- Publisher backend URL: `ws://<VPS_PUBLIC_IP>/ws/publisher`
- Listener browser URL: `http://<VPS_PUBLIC_IP>/`

Publisher writes detailed connection and exception diagnostics to `logs.txt`:

- When running the packaged `.exe`, `logs.txt` is next to the executable.
- When running from source, it is `src/publisher/logs.txt`.

Collect the VPS service state, sanitized configuration, recent JSONL logs, port
listeners, Listener file permissions, and HTTP checks with:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh
```

The script saves its report under
`/tmp/byod-diagnostics-<timestamp>/`. It redacts configured API secrets and the
default PIN, but review the report before downloading or sharing it.

If Publisher reports `CONNECTION ERROR`, check in this order:

1. Confirm the Publisher URL is exactly
   `ws://<VPS_PUBLIC_IP>/ws/publisher` (no port `8000`).
2. Open `http://<VPS_PUBLIC_IP>/health` from the operator workstation.
3. Run the diagnostic collection command above.
4. Review Publisher `logs.txt`, then the backend JSONL and journal sections in
   the collected report for the last error stage, schema rejection, LiveKit
   host/port reachability result, or WebSocket close code.
5. Verify again that the backend and LiveKit API key/secret values match
   exactly and that Windows CRLF characters were removed.

## 9) Manifest

Use `deploy/stage_x_ubuntu_pilot/manifest.yaml` as single source of truth for:

- pinned versions
- artifact paths
- fallback URL
- rollback reference
