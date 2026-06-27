# 21. Backend Logging Contract (Stage X Pilot)

This contract defines minimum logs for pilot diagnostics.

## 1) Log streams

1. **Service logs (systemd files)**
   - `/opt/byod/logs/backend.stdout.log`
   - `/opt/byod/logs/backend.stderr.log`

2. **Structured JSONL event logs**
   - `/opt/byod/backend_data/events_log_YYYYMMDD.jsonl`
   - `/opt/byod/backend_data/connections_log_YYYYMMDD.jsonl`

## 2) Required fields in JSONL events

Every event line must include:

- `ts` (unix seconds)
- `ts_iso_msk` (Europe/Moscow ISO timestamp without milliseconds, for example `2026-06-27T21:15:30+03:00`)
- `event` (stable event name)

Optional fields can include:

- `request_id`
- `publisher_id`
- `listener_id`
- `channel_id`
- `context`
- `livekit_url`

## 3) Required Stage X diagnostic events

- `backend_started`
- `bootstrap_defaults_applied`
- `publisher_connected`
- `listener_connected`
- `publisher_disconnected`
- `listener_disconnected`
- `room_status_changed`
- `livekit_unreachable`

## 4) LiveKit failure logging rule

When backend cannot proceed because LiveKit is unreachable,
backend must write `livekit_unreachable` to `events_log_*.jsonl`.

Recommended contexts:

- `publisher_connecting`
- `publisher_on_air`
- `listener_connecting`

## 5) Operator usage

For quick incident checks, operator reads newest lines with:

```bash
tail -n 100 /opt/byod/backend_data/events_log_$(date -u +%Y%m%d).jsonl
```
