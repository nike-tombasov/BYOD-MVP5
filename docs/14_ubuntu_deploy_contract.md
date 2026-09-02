# 14. Ubuntu deploy contract

This document is the canonical BYOD project/spec contract for the current single-node Ubuntu VPS deploy package in `deploy/stage_x_ubuntu_pilot/`. It records deployment structure, invariants, generated files, service boundaries, and known constraints. It is not an operator runbook; step-by-step VPS commands remain in the deploy package operator docs.

## Target platform

Target platform: Ubuntu Server 22.04 LTS or compatible systemd-based Ubuntu VPS.

## Filesystem layout

The deploy scripts currently create and use this `/opt/byod` layout:

| Path | Contract |
|---|---|
| `/opt/byod/app` | Runtime application copy used by systemd services. |
| `/opt/byod/config` | Private runtime configuration (`backend.env`, `livekit.yaml`); not public web assets. |
| `/opt/byod/backend_data` | Persistent backend room/runtime/recording state and backend JSONL structured logs. |
| `/opt/byod/livekit` | LiveKit binary installation location. |
| `/opt/byod/listener` | Listener static web assets served by nginx. |
| `/opt/byod/releases` | Release artifacts used during install, including LiveKit archive/checksum. |
| `/opt/byod/logs` | Backend and LiveKit stdout/stderr service logs. |
| `/opt/byod/metrics` | Metrics analyzer output directory. |
| `/opt/byod/diagnostics` | Diagnostic and smoke-test output location. Current smoke/diagnostic scripts create it when collecting output; it is not created by `00_prepare_host.sh`. |

Related source checkout convention: `/opt/byod/app-src` is the expected VPS source checkout path used by helper examples and operator docs. It is not created by `00_prepare_host.sh`; the deploy is run from the checked-out repository and copies runtime files into `/opt/byod/app`.

## Service user and ownership model

The service user is `byod`. Host preparation creates it as a system user with home `/opt/byod` and nologin shell, creates the runtime directories, assigns `/opt/byod` ownership to `byod:byod`, and restricts private config/data/log/metrics directories.

Backend and LiveKit runtime files and configs are owned by `byod` and systemd runs `byod-backend` and `byod-livekit` as `User=byod`/`Group=byod`. Listener static files under `/opt/byod/listener` are installed with mode `0755` so nginx (`www-data`) and the public web server path can read them. Files under `/opt/byod/config` are private runtime config, not public web assets.

## Public/private network boundary

The backend always binds privately to `127.0.0.1:8000`; provider firewalls must not expose `8000/tcp`. Backend `/admin/*` endpoints are local-only and nginx must never proxy them publicly.

### Direct-IP mode

- nginx serves public HTTP on port 80;
- public nginx paths are `/`, `/listener.js`, `/vendor/*`, `/ws/listener`, `/ws/publisher`, and `/health`;
- other Listener paths return `404`;
- LiveKit signaling is public at `ws://<ip>:7880`;
- public ports are `80/tcp`, `7880/tcp`, `7881/tcp`, and `50000-59999/udp`.

### Domain HTTPS/WSS mode

- the `listen-*` host serves Listener HTTPS plus `/ws/listener` and `/ws/publisher` through nginx;
- the `lk-*` host proxies HTTPS/WSS signaling to local LiveKit at `127.0.0.1:7880`;
- optional `admin-*` is reserved and returns `404`;
- root `/` remains public, and validated room config may enable exactly one `/<subsite_name>/` Listener alias;
- `subsite_name` is not DNS or multi-room routing; wrong and old aliases return `404`;
- public ports are `80/tcp`, `443/tcp`, `7881/tcp`, and `50000-59999/udp`.

## LiveKit config contract

The generated `/opt/byod/config/livekit.yaml` contract is:

```yaml
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 59999
  use_external_ip: true
```

The package also contains `deploy/stage_x_ubuntu_pilot/config/livekit_udp_mux_7882.yaml`. That fallback UDP mux profile exists only for diagnostics/provider UDP range problems; it is not the normal deploy contract.

## nginx and systemd limits

The packaged nginx main config at `deploy/stage_x_ubuntu_pilot/nginx/nginx.conf` sets:

```text
worker_connections=65535
```

The packaged nginx systemd override at `deploy/stage_x_ubuntu_pilot/systemd/nginx.service.d/override.conf` sets:

```text
LimitNOFILE=200000
```

`byod-backend.service` also sets `LimitNOFILE=200000`. `byod-livekit.service` currently sets `LimitNOFILE=65535`.

## systemd services

| Service | Role | Public-facing status |
|---|---|---|
| `nginx` | Serves Listener static assets and proxies public backend paths. | Public HTTP/WebSocket entrypoint on port 80. |
| `byod-backend` | FastAPI/uvicorn backend for health, public WebSocket paths, local admin endpoints, state, and tokens. | Local backend process bound to `127.0.0.1:8000`; public access only through nginx-approved paths. |
| `byod-livekit` | Self-hosted LiveKit server using `/opt/byod/config/livekit.yaml`. | Direct-IP signaling is public at `ws://<ip>:7880`; domain-mode signaling is `wss://lk-*` through nginx to local `127.0.0.1:7880`. LiveKit media/RTC ports remain separate according to the mode-specific port model above. |
| `byod-metrics-analyzer` | Optional analyzer service generated by `95_metrics_analyzer.sh`; writes metrics samples under `/opt/byod/metrics`. | Internal diagnostics service, not public-facing. |

## Canonical deploy script order

`01_one_deploy_from_vps_config.sh` is the canonical one-command orchestrator:

1. prepare the host;
2. install LiveKit, backend, and Listener;
3. generate backend and LiveKit runtime config;
4. install the optional Listener vendor file;
5. enable and start services;
6. import `/tmp/room_input.json` through backend validation when present (or clear the alias and restart backend when absent);
7. in domain mode, run DNS preflight and TLS/nginx setup using validated/persisted `subsite_name`;
8. apply the stress profile if explicitly enabled;
9. run the smoke test.

TLS/nginx rendering must never enable an alias before room import validation succeeds.

## Config contract

| Path | Contract |
|---|---|
| `/tmp/vps_config.env` | Deploy input/preconfig consumed by the orchestrator. |
| `/opt/byod/config/backend.env` | Generated backend runtime environment for `byod-backend`. |
| `/opt/byod/config/livekit.yaml` | Generated LiveKit runtime config for `byod-livekit`. |
| `/opt/byod/backend_data/*.json` | Persisted backend room/runtime/recording state. |
| `/tmp/room_input.json` | Optional deploy-time room config import input. |

## Diagnostics and log locations

Location contract:

```text
/opt/byod/diagnostics
/opt/byod/metrics
/opt/byod/logs
/opt/byod/backend_data/*_log_*.jsonl
/var/log/nginx/*
journalctl for systemd services
```

These locations are for diagnostics and evidence collection; incident procedures remain in operator docs under `deploy/stage_x_ubuntu_pilot/docs/`.

## Open issue / rollback note

Current deploy replaces or installs nginx BYOD site config as part of VPS setup, including the packaged main nginx config and BYOD site. Rollback behavior for pre-existing nginx configs must be treated carefully. Exact rollback policy should remain explicit in operator docs and/or a future hardening task. This contract records the current deployment expectation but does not claim a universal safe rollback for arbitrary pre-existing nginx servers.
