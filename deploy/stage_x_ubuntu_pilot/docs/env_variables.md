# Stage X Environment Variables

Source template: `.env.example`.

| Variable | Required | Purpose | Example |
|---|---|---|---|
| `BYOD_LIVEKIT_URL` | Yes | LiveKit ws/wss URL sent to clients and used for health check. | `ws://<VPS_PUBLIC_IP>:7880` |
| `BYOD_LIVEKIT_API_KEY` | Yes | API key for JWT creation. | `pilot_key` |
| `BYOD_LIVEKIT_API_SECRET` | Yes | API secret for JWT creation. Keep private. | `long_secret_value` |
| `BYOD_BACKEND_HOST` | Yes | Backend bind host for uvicorn. | `127.0.0.1` |
| `BYOD_BACKEND_PORT` | Yes | Backend bind port for uvicorn. | `8000` |
| `BYOD_CORS_ALLOWED_ORIGIN` | Yes | Only listener page origin allowed by CORS. | `http://<VPS_PUBLIC_IP>` |
| `BYOD_DATA_DIR` | Yes | Base folder for backend JSON state and logs. | `/opt/byod/backend_data` |
| `BYOD_ROOM_CONFIG_PATH` | Yes | Room config JSON file path. | `/opt/byod/backend_data/room_config_v1.json` |
| `BYOD_RUNTIME_STATE_PATH` | Yes | Runtime state JSON file path. | `/opt/byod/backend_data/runtime_state_v1.json` |
| `BYOD_RECORDING_STATE_PATH` | Yes | Recording markers JSON file path. | `/opt/byod/backend_data/recording_state_v1.json` |
| `BYOD_DEFAULT_PIN` | Optional | Bootstrap PIN on clean deploy only. | `123456` |
| `BYOD_TARGET_CAPACITY` | Optional | Bootstrap target listener capacity (pilot fixed to 200). | `200` |
| `BYOD_MAX_ACTIVE_LISTENERS` | Optional | Override for active Listener sessions. Empty means derive from `target_capacity`. | `500` |
| `BYOD_MAX_NEW_CONNECTIONS_PER_SEC` | Optional | Override for global new Listener connections per second. Empty means derive from `target_capacity`. | `50` |
| `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` | Optional | Per-IP Listener connect/reconnect throttle. Important for NAT/public Wi-Fi and stress tests. | `2` |
| `BYOD_LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS` | Optional | TCP probe timeout for LiveKit reachability checks. | `1.5` |

Notes:
- Clean deploy default `room_status` remains `BLOCKED`.
- Bootstrap defaults are used only when no persisted room config exists.
- For the IP-only pilot, use `BYOD_LIVEKIT_URL=ws://<VPS_PUBLIC_IP>:7880` and
  `BYOD_CORS_ALLOWED_ORIGIN=http://<VPS_PUBLIC_IP>`.
- `BYOD_LIVEKIT_API_KEY` and `BYOD_LIVEKIT_API_SECRET` must exactly match the
  key and secret under `keys:` in `/opt/byod/config/livekit.yaml`.
- Plain HTTP/WS is acceptable only for today's IP pilot. Move a later
  production/domain deployment to TLS with HTTPS/WSS.
