# BYOD VPS Configuration Reference

## Required `/tmp` deploy files

- `/tmp/vps_config.env` — shell-compatible deploy config.
- `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz` — LiveKit server archive.
- `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256` — SHA-256 checksum file for the archive.

Optional:

- `/tmp/room_input.json` — room config imported through backend validation when present.
- `/tmp/livekit-client.umd.1.15.13.js` — pinned Listener browser SDK fallback file.

## `/tmp/vps_config.env` schema

| Variable | Required | Purpose |
|---|---:|---|
| `BYOD_REPO_URL` | Yes | Git repository URL cloned by the bootstrap command. |
| `BYOD_REPO_BRANCH` | Yes | Branch to clone into `/opt/byod/app-src`. |
| `BYOD_VPS_PUBLIC_IP` | Yes | Public IPv4 used by operator notes and diagnostics. |
| `BYOD_DOMAIN_TLS_MODE` | No | Strict `true`/`false`; defaults to `false` (direct-IP mode). |
| `BYOD_LISTENER_DOMAIN` | Domain mode | Guest Listener hostname only, without scheme, port, or path. |
| `BYOD_LIVEKIT_DOMAIN` | Domain mode | LiveKit signaling hostname only, without scheme, port, or path. |
| `BYOD_ADMIN_DOMAIN` | No | Optional reserved future Admin UI hostname; it returns `404`. |
| `BYOD_TLS_EMAIL` | Domain mode | Email used for Let's Encrypt registration. |
| `BYOD_PUBLIC_ORIGIN` | Yes | Public browser origin, for example `http://203.0.113.10`. It should be an origin without a path; one trailing slash is normalized by the deploy script. |
| `BYOD_LIVEKIT_URL` | Yes | LiveKit URL sent to clients, for example `ws://203.0.113.10:7880`. |
| `BYOD_LIVEKIT_API_KEY` | Yes | LiveKit API key. |
| `BYOD_LIVEKIT_API_SECRET` | Yes | LiveKit API secret; never print in full. |
| `BYOD_BACKEND_HOST` | Yes | Backend bind host. Use `127.0.0.1`. |
| `BYOD_BACKEND_PORT` | Yes | Backend bind port. Use `8000`. |
| `BYOD_DEFAULT_PIN` | No | Clean-deploy bootstrap PIN. Defaults to `123456` if omitted. |
| `BYOD_ENABLE_BACKEND_STRESS_TEST` | No | Deploy-time switch for applying the temporary backend stress profile before final smoke test. Supported: `true`/`false` plus `1`/`0`, `yes`/`no`, `on`/`off`. Defaults to `false`. |
| `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` | No | Per-IP Listener connect/reconnect throttle in seconds. Integer `>= 0`; `0` disables this specific throttle. Defaults to `2`. |
| `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` | No | Optional global Listener admission-rate override. Empty/unset means backend derives `max_new_connections_per_sec` from `target_capacity`. Set an integer `>= 1` only for temporary tuning after VPS sizing/stress testing. |
| `BYOD_ROOM_INPUT_PATH` | No | Defaults to `/tmp/room_input.json`. |
| `BYOD_LIVEKIT_TGZ_PATH` | No | Defaults to `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz`. |
| `BYOD_LIVEKIT_SHA256_PATH` | No | Defaults to `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`. |
| `BYOD_LISTENER_VENDOR_PATH` | No | Defaults to `/tmp/livekit-client.umd.1.15.13.js`. |

## Full sample `/tmp/vps_config.env`

```bash
BYOD_REPO_URL="https://github.com/nike-tombasov/BYOD-MVP5.git"
BYOD_REPO_BRANCH="codex-qv5tz8"
BYOD_VPS_PUBLIC_IP="203.0.113.10"
BYOD_DOMAIN_TLS_MODE=false
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

## Domain HTTPS/WSS sample

```bash
BYOD_REPO_URL="https://github.com/nike-tombasov/BYOD-MVP5.git"
BYOD_REPO_BRANCH="MVP11"
BYOD_VPS_PUBLIC_IP="194.58.118.140"
BYOD_DOMAIN_TLS_MODE=true
BYOD_LISTENER_DOMAIN="listen-1.k-pls.ru"
BYOD_LIVEKIT_DOMAIN="lk-1.k-pls.ru"
BYOD_ADMIN_DOMAIN="admin-1.k-pls.ru"
BYOD_TLS_EMAIL="replace@example.com"
BYOD_PUBLIC_ORIGIN="https://listen-1.k-pls.ru"
BYOD_LIVEKIT_URL="wss://lk-1.k-pls.ru"
BYOD_LIVEKIT_API_KEY="replace_with_livekit_key"
BYOD_LIVEKIT_API_SECRET="replace_with_long_livekit_secret"
BYOD_BACKEND_HOST="127.0.0.1"
BYOD_BACKEND_PORT="8000"
BYOD_DEFAULT_PIN="123456"
BYOD_ENABLE_BACKEND_STRESS_TEST=false
BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS=0
BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE=""
```

The reconnect interval `0` is recommended for guest mobile networks, CGNAT, and public Wi-Fi, where many clients can share an address.

## Validation rules

Domain mode requires `BYOD_LISTENER_DOMAIN`, `BYOD_LIVEKIT_DOMAIN`, and `BYOD_TLS_EMAIL`; `BYOD_ADMIN_DOMAIN` is optional. Domains must be hostname-only values. The origins must be path-free exact values `https://$BYOD_LISTENER_DOMAIN` and `wss://$BYOD_LIVEKIT_DOMAIN`. DNS preflight requires each configured name to resolve to `BYOD_VPS_PUBLIC_IP` before certbot runs. Direct-IP mode requires none of these optional values.

- Required values must be present and non-empty.
- `BYOD_BACKEND_PORT` must be an integer.
- `BYOD_ENABLE_BACKEND_STRESS_TEST` must be a clear boolean: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`.
- `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` must be an integer `>= 0`.
- `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` must be empty or an integer `>= 1`.
- `BYOD_PUBLIC_ORIGIN` must start with `http://` or `https://`.
- `BYOD_LIVEKIT_URL` must start with `ws://` or `wss://`.
- CRLF is removed before `source`; generated config files are also normalized to LF.
- LiveKit archive and checksum are mandatory for a clean deploy and are verified before install.
- Logs redact `BYOD_LIVEKIT_API_SECRET`.

## Generated `/opt/byod/config/backend.env` mapping

| Generated variable | Source |
|---|---|
| `BYOD_LIVEKIT_URL` | `BYOD_LIVEKIT_URL` |
| `BYOD_LIVEKIT_API_KEY` | `BYOD_LIVEKIT_API_KEY` |
| `BYOD_LIVEKIT_API_SECRET` | `BYOD_LIVEKIT_API_SECRET` |
| `BYOD_BACKEND_HOST` | `BYOD_BACKEND_HOST` |
| `BYOD_BACKEND_PORT` | `BYOD_BACKEND_PORT` |
| `BYOD_CORS_ALLOWED_ORIGIN` | `BYOD_PUBLIC_ORIGIN` |
| `BYOD_DEFAULT_PIN` | `BYOD_DEFAULT_PIN` or default `123456` |
| `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` | `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` or default `2` |
| `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` | `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` or empty |
| `BYOD_DATA_DIR` and state paths | Fixed `/opt/byod/backend_data` paths |

## Backend capacity/admission variables

Normal event sizing should come from `target_capacity` in `/tmp/room_input.json`; the backend derives active-listener and new-connection limits from that room JSON unless a temporary override is set. Do not add `BYOD_DEFAULT_TARGET_CAPACITY` to normal VPS config for now: the code fallback is only for clean deploy/no import.

`/tmp/vps_config.env` carries the per-IP reconnect throttle (`BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS`), the optional global admission-rate override (`BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE`), and the optional deploy switch (`BYOD_ENABLE_BACKEND_STRESS_TEST`). Stress profile overrides live in `deploy/stage_x_ubuntu_pilot/config/backend_stress_test.env` and are applied by `68_apply_backend_stress_profile.sh` when explicitly enabled or run manually.

To change connection admission speed on an already deployed VPS, edit `/opt/byod/config/backend.env`, set `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` to an integer `>= 1`, and restart `byod-backend`. Clear it back to an empty string to return to room-config-derived behavior.

## Generated `/opt/byod/config/livekit.yaml` mapping

- `port: 7880`
- `bind_addresses: ["0.0.0.0"]`
- `rtc.tcp_port: 7881`
- `rtc.port_range_start: 50000`
- `rtc.port_range_end: 59999`
- `rtc.use_external_ip: true`
- `keys` contains `BYOD_LIVEKIT_API_KEY: BYOD_LIVEKIT_API_SECRET` with JSON/YAML-safe string quoting.

## `/tmp/room_input.json`

When present, the orchestrator uploads it to `http://127.0.0.1:8000/admin/import_json` as multipart form data. Validation is performed by the backend importer (`parse_room_config_json_bytes`). Invalid input returns `ok: false` and fails deploy.

## Security notes

- Run `sudo chmod 600 /tmp/vps_config.env` after upload.
- Never paste real secrets into tickets, screenshots, or shared logs.
- Backend port `8000/tcp` must remain closed publicly.
- `/admin/*` endpoints are local-only and must not be proxied through nginx.
