# Stage X Ubuntu Pilot Deploy Guide

This guide is for a fresh **Ubuntu 22.04 LTS** VPS with one public IPv4.

## 1) Bootstrap the clean VPS and clone branch MVP10

```bash
sudo apt-get update
sudo apt-get install -y git
sudo mkdir -p /opt/byod
sudo chown "$USER:$USER" /opt/byod
git clone --branch MVP10 <your_repo_url> /opt/byod/app-src
cd /opt/byod/app-src
sudo bash deploy/stage_x_ubuntu_pilot/scripts/00_prepare_host.sh
```

The prepare script installs the remaining host packages (and ensures `git` is
present), creates the `byod` service account, and creates these directories:

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

Example commands on operator laptop:

```bash
curl -fL https://github.com/livekit/livekit/releases/download/v1.9.11/livekit-server-v1.9.11-linux-amd64.tar.gz -o livekit-server-v1.9.11-linux-amd64.tar.gz
sha256sum livekit-server-v1.9.11-linux-amd64.tar.gz > livekit-server-v1.9.11-linux-amd64.tar.gz.sha256
```

Upload both files to `/tmp` first; a regular SSH user cannot write directly to
the service-owned release directory after host preparation:

```bash
scp livekit-server-v1.9.11-linux-amd64.tar.gz <user>@<vps_ip>:/tmp/
scp livekit-server-v1.9.11-linux-amd64.tar.gz.sha256 <user>@<vps_ip>:/tmp/
ssh <user>@<vps_ip>
sudo mv /tmp/livekit-server-v1.9.11-linux-amd64.tar.gz* /opt/byod/releases/
sudo chown byod:byod /opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz*
cd /opt/byod/app-src
```

PuTTY/WinSCP users can upload both artifacts to `/tmp` with WinSCP, then open
PuTTY and run the same `sudo mv`, `sudo chown`, and `cd` commands shown above.

Install LiveKit:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/10_install_livekit.sh
```

Fallback:
- If custom artifact is not present, script downloads from official GitHub release URL.

## 3) Install backend and listener

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
- `BYOD_TARGET_CAPACITY=200`

Edit LiveKit config:

```bash
sudo nano /opt/byod/config/livekit.yaml
```

Replace API key/secret values in `keys:`. The key and secret must exactly match
`BYOD_LIVEKIT_API_KEY` and `BYOD_LIVEKIT_API_SECRET` in `backend.env`.

## 5) Enable services and nginx

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/40_enable_services.sh
```

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

Then perform the public client checks:

1. Open `http://<VPS_PUBLIC_IP>/` in a browser and confirm the listener
   connects.
2. Start Publisher and manually replace its default localhost backend value
   with `ws://<VPS_PUBLIC_IP>/ws/publisher` before connecting. The Publisher's
   default `ws://127.0.0.1:8000/ws/publisher` value is only suitable when the
   backend runs on the same machine, not for VPS testing.

The IP/HTTP setup is acceptable only for this pilot. A production or
domain-based deployment should add TLS and use HTTPS/WSS.

## 8) Manifest

Use `deploy/stage_x_ubuntu_pilot/manifest.yaml` as single source of truth for:

- pinned versions
- artifact paths
- fallback URL
- rollback reference
