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
| `BYOD_PUBLIC_ORIGIN` | Yes | Public browser origin, for example `http://203.0.113.10`. |
| `BYOD_LIVEKIT_URL` | Yes | LiveKit URL sent to clients, for example `ws://203.0.113.10:7880`. |
| `BYOD_LIVEKIT_API_KEY` | Yes | LiveKit API key. |
| `BYOD_LIVEKIT_API_SECRET` | Yes | LiveKit API secret; never print in full. |
| `BYOD_BACKEND_HOST` | Yes | Backend bind host. Use `127.0.0.1`. |
| `BYOD_BACKEND_PORT` | Yes | Backend bind port. Use `8000`. |
| `BYOD_DEFAULT_PIN` | No | Clean-deploy bootstrap PIN. Defaults to `123456` if omitted. |
| `BYOD_ROOM_INPUT_PATH` | No | Defaults to `/tmp/room_input.json`. |
| `BYOD_LIVEKIT_TGZ_PATH` | No | Defaults to `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz`. |
| `BYOD_LIVEKIT_SHA256_PATH` | No | Defaults to `/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`. |
| `BYOD_LISTENER_VENDOR_PATH` | No | Defaults to `/tmp/livekit-client.umd.1.15.13.js`. |

## Full sample `/tmp/vps_config.env`

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
BYOD_ROOM_INPUT_PATH="/tmp/room_input.json"
BYOD_LIVEKIT_TGZ_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz"
BYOD_LIVEKIT_SHA256_PATH="/tmp/livekit-server-v1.9.11-linux-amd64.tar.gz.sha256"
BYOD_LISTENER_VENDOR_PATH="/tmp/livekit-client.umd.1.15.13.js"
```

## Validation rules

- Required values must be present and non-empty.
- `BYOD_BACKEND_PORT` must be an integer.
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
| `BYOD_DATA_DIR` and state paths | Fixed `/opt/byod/backend_data` paths |

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
