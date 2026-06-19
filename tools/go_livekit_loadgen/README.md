# BYOD Go LiveKit loadgen

This directory is the active future loadgen path described by `docs/22_stress_tests.md`. The legacy Python loader under `legacy/stage_xi_failed_python_loader/` is forensic reference only and is not imported, wrapped, or reused here.

This PR implements **Gate A only**: `backend-ws-only`. Gate B (`livekit-connect-only`) and Gate C (`livekit-subscribe-discard-rtp`) are intentionally documented but not implemented yet. Gate A opens backend listener WebSockets, sends the normal listener `connecting` envelope plus diagnostic metadata, maintains backend heartbeats during HOLD, and never connects to LiveKit.

Windows is the primary operator environment. The PowerShell helpers in `scripts/` are convenience wrappers around `go run ./cmd/byod-loadgen` and keep important flags visible.

## Profiles

- `local-direct` bypasses nginx and targets the backend directly, for example `http://127.0.0.1:8000` resolves to `ws://127.0.0.1:8000/ws/listener`.
- `vps-nginx` includes nginx in the backend WebSocket path and targets `ws://<host>/ws/listener` from `http://<VPS_PUBLIC_IP>`.

## Run examples

```powershell
go run ./cmd/byod-loadgen `
  -profile local-direct `
  -mode backend-ws-only `
  -server http://127.0.0.1:8000 `
  -listeners 10 `
  -ramp-per-sec 5 `
  -hold-sec 60 `
  -runner-id win-dev-1 `
  -loadgen-key byod_loadgen_key_01
```

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode backend-ws-only `
  -server http://<VPS_PUBLIC_IP> `
  -listeners 500 `
  -ramp-per-sec 50 `
  -hold-sec 600 `
  -runner-id win-home-1 `
  -loadgen-key byod_loadgen_key_01
```

Output is written under `-out-dir` (default `./out`) as `events_<timestamp>.jsonl` and `summary_<timestamp>.json`. Timestamps use `ts_iso` in Moscow time (`+03:00`) rounded to tenths of a second.

The loadgen key is not a password. It is a stress-event guard combined with backend-side enablement. Running the Go loadgen with `byod_loadgen_key_01` alone does nothing unless the backend operator explicitly enables the reconnect throttle bypass.

To enable the temporary backend per-IP reconnect bypass for a stress event, set these backend environment overrides and restart the backend service:

```text
BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED=true
BYOD_LOADGEN_RECONNECT_BYPASS_KEY=byod_loadgen_key_01
```

Disable it after the stress run by removing the overrides or setting `BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED=false`, then restart the backend service. The bypass only affects `RECONNECT_TOO_FAST`; max active listeners, connection rate limits, malformed message handling, and normal listener protocol still apply.

TCP/UDP ratio is `n/a` in Gate A because LiveKit is not used.
