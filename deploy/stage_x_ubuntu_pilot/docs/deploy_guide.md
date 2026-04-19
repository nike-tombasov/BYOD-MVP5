# Stage X Ubuntu Pilot Deploy Guide

This guide is for a fresh **Ubuntu 22.04 LTS** VPS with one public IPv4.

## 1) Copy repository to VPS

```bash
git clone <your_repo_url> /opt/byod/app-src
cd /opt/byod/app-src
```

## 2) Prepare host (idempotent)

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/00_prepare_host.sh
```

This creates required directories:

- `/opt/byod/app`
- `/opt/byod/config`
- `/opt/byod/livekit`
- `/opt/byod/listener`
- `/opt/byod/backend_data`
- `/opt/byod/logs`
- `/opt/byod/releases`

## 3) Put LiveKit pinned artifact + checksum (preferred)

Expected files before install:

- `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz`
- `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`

Example commands on operator laptop:

```bash
curl -fL https://github.com/livekit/livekit/releases/download/v1.9.11/livekit-server-v1.9.11-linux-amd64.tar.gz -o livekit-server-v1.9.11-linux-amd64.tar.gz
sha256sum livekit-server-v1.9.11-linux-amd64.tar.gz > livekit-server-v1.9.11-linux-amd64.tar.gz.sha256
```

Upload both files to VPS:

```bash
scp livekit-server-v1.9.11-linux-amd64.tar.gz <user>@<vps_ip>:/opt/byod/releases/
scp livekit-server-v1.9.11-linux-amd64.tar.gz.sha256 <user>@<vps_ip>:/opt/byod/releases/
```

Install LiveKit:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/10_install_livekit.sh
```

Fallback:
- If custom artifact is not present, script downloads from official GitHub release URL.

## 4) Install backend and listener

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/20_install_backend.sh
sudo bash deploy/stage_x_ubuntu_pilot/scripts/30_install_listener.sh
```

Notes:
- Backend installs **backend-only** Python requirements.
- `/opt/byod/config/livekit.yaml` is auto-created from template if missing (existing file is not overwritten).

## 5) Configure pilot values

Edit backend env file:

```bash
sudo nano /opt/byod/config/backend.env
```

Set at least:

- `BYOD_LIVEKIT_URL`
- `BYOD_LIVEKIT_API_KEY`
- `BYOD_LIVEKIT_API_SECRET`
- `BYOD_CORS_ALLOWED_ORIGIN` (single listener origin)
- `BYOD_TARGET_CAPACITY=200`

Edit LiveKit config:

```bash
sudo nano /opt/byod/config/livekit.yaml
```

Replace API key/secret values in `keys:`.

## 6) Enable services and nginx

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/40_enable_services.sh
```

## 7) Run smoke test

```bash
bash deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh
```

## 8) Manifest

Use `deploy/stage_x_ubuntu_pilot/manifest.yaml` as single source of truth for:

- pinned versions
- artifact paths
- fallback URL
- rollback reference
