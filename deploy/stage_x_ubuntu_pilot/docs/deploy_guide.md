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

## 3) Put LiveKit pinned artifact (preferred)

Preferred:

1. Upload artifact to `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz`
2. Upload checksum file to `/opt/byod/releases/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`

Then run:

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

Copy template first if needed:

```bash
sudo cp deploy/stage_x_ubuntu_pilot/config/livekit.yaml /opt/byod/config/livekit.yaml
```

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
