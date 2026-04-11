## 17. Backend persistence JSON schema v1

Goal:
- make Stage VII backend JSON persistence deterministic and auditable;
- avoid data-loss ambiguity during restart/crash;
- keep MVP persistence simple for first VPS cycle.

---

### 17.1 Storage layout

Root folder:
`backend_data/`

Files:
- `room_config_v1.json` — room static/semi-static config (PIN, room_name, channels, labels, listen flags).
- `runtime_state_v1.json` — current runtime snapshot (room_status, owner map, overrides).
- `connections_log_YYYYMMDD.jsonl` — append-only connection events (publisher/listener connect/disconnect).
- `events_log_YYYYMMDD.jsonl` — append-only operational events (on_air/stop/status changes/override commands).
- `recording_state_v1.json` — recording on/off snapshot and active files metadata.

JSONL format:
- one JSON object per line, UTF-8.

---

### 17.2 Atomic write rule

For non-log files:
1) write to `*.tmp`
2) flush + fsync
3) atomic rename to target file

For log files:
- append-only write;
- flush at least every N events or 1 second (configurable);
- on startup ignore last corrupted partial line if crash occurred.

---

### 17.3 `room_config_v1.json` (example)

```json
{
  "schema_version": 1,
  "room_id": "room_main",
  "pin": "123456",
  "room_name": "Main Hall",
  "target_capacity": 300,
  "channels": [
    {"channel_id": "channel_0", "channel_label": "Floor", "listen": false},
    {"channel_id": "channel_1", "channel_label": "English", "listen": true}
  ],
  "updated_ts": 1710000000
}
```

Rules:
- `channel_id` unique.
- `channel_0.listen` default false.
- reserve channels follow deployment policy.
- `target_capacity` immutable for current event runtime.

---

### 17.4 `runtime_state_v1.json` (example)

```json
{
  "schema_version": 1,
  "room_status": "OPENED",
  "owners": {
    "channel_0": null,
    "channel_1": "hostA_0"
  },
  "publisher_online": {
    "hostA_0": true
  },
  "overrides": {
    "blocked": null,
    "closed": null
  },
  "updated_ts": 1710000100
}
```

Rules:
- this file is recoverable snapshot only (source of truth during runtime remains in-memory backend state);
- loaded at startup to restore operational continuity.

---

### 17.5 Logs (JSONL event contract)

`connections_log_*.jsonl` line example:
```json
{"ts":1710000110,"event":"publisher_connected","publisher_id":"hostA_0","ip":"10.0.0.12:53321"}
```

`events_log_*.jsonl` line example:
```json
{"ts":1710000120,"event":"on_air_granted","publisher_id":"hostA_0","channel_id":"channel_1","request_id":"onair-req-5"}
```

Mandatory event fields:
- `ts`, `event`, `request_id` (if WS-linked), `actor_id`/`client_id` when applicable.

---

### 17.6 Retention and rotation

Baseline policy (MVP):
- rotate JSONL daily (UTC).
- keep hot logs locally 14 days.
- optional archive/export by operator.
- if disk free space < 15%: emit critical warning; if < 10%: stop new recordings before state/log writes fail.

---

### 17.7 Startup recovery order

1) load `room_config_v1.json`
2) load `runtime_state_v1.json` (if exists)
3) rebuild in-memory state
4) open new JSONL log files for current day
5) append `backend_started` event

---
