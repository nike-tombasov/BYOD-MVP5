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
- `room_config_v1.json` — room static/semi-static config (PIN, `subsite_name`, channels, labels, listen flags, immutable i18n library, capacity).
- `runtime_state_v1.json` — current runtime snapshot (room_status, owner map, online counters).
- `connections_log_YYYYMMDD.jsonl` — append-only connection events (publisher/listener connect/disconnect).
- `events_log_YYYYMMDD.jsonl` — append-only operational events (on_air/stop/status changes).
- `recording_state_v1.json` — recording on/off snapshot and active files metadata.

JSONL format:
- one JSON object per line, UTF-8.

---

### 17.2 Atomic write rule

For non-log files:
1) write to `*.tmp`
2) flush + fsync
3) atomic rename to target file

For log files (current Stage VII implementation):
- append-only write;
- flush on every appended event line;
- startup partial-line recovery/truncation is not implemented yet (known limitation for next stages).

---

### 17.3 `room_config_v1.json` (example)

```json
{
  "schema_version": 1,
  "room_id": "room_main",
  "subsite_name": "test-conf",
  "pin": "123456",
  "target_capacity": 200,
  "channels": [
    {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": false},
    {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": true},
    {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": true},
    {"channel_id": "channel_3", "channel_label": "Reserve 1", "listen": false},
    {"channel_id": "channel_4", "channel_label": "Reserve 2", "listen": false}
  ],
  "i18n_library": {
    "room_name_i18n": {
      "en": "Conference room",
      "ru": "Зал конференции"
    },
    "custom_status_text_blocked_i18n": {
      "en": "Stream temporarily stopped",
      "ru": "Трансляция временно остановлена"
    },
    "custom_status_text_closed_i18n": {
      "en": "The conference is over. Thank you for your participation",
      "ru": "Конференция окончена. Благодарим за участие"
    }
  },
  "updated_ts": 1710000000
}
```

Rules:
- `subsite_name` is persisted with room metadata; absent or `null` means no Listener alias.
- Old persisted configs without `subsite_name` remain compatible and load as no alias.
- A successful JSON import replaces `subsite_name` together with the room snapshot; it is never merged with the previous alias.
- `channel_id` unique.
- `channel_0.listen` default false.
- `target_capacity` immutable for current event runtime.
- `i18n_library` is deploy/runtime immutable base dictionary set (changes only by import/redeploy policy).

---

### 17.4 Deployment immutable default metadata (bootstrap before first successful JSON import)

Backend MUST use this immutable bootstrap default at deploy-time before first JSON import:

```json
{
  "subsite_name": null,
  "target_capacity": 200,
  "pin": "123456",
  "channels": [
    {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": false},
    {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": true},
    {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": true},
    {"channel_id": "channel_3", "channel_label": "Reserve 1", "listen": false},
    {"channel_id": "channel_4", "channel_label": "Reserve 2", "listen": false}
  ],
  "i18n_library": {
    "room_name_i18n": {
      "en": "Conference room",
      "ru": "Зал конференции"
    },
    "custom_status_text_blocked_i18n": {
      "en": "Stream temporarily stopped",
      "ru": "Трансляция временно остановлена"
    },
    "custom_status_text_closed_i18n": {
      "en": "The conference is over. Thank you for your participation",
      "ru": "Конференция окончена. Благодарим за участие"
    }
  }
}
```

Bootstrap default applies only before first successful JSON import.
After successful JSON import backend keeps imported metadata across VPS/backend restart.
Default runtime room status on clean deploy: `BLOCKED`.

---

### 17.5 `runtime_state_v1.json` (example)

```json
{
  "schema_version": 1,
  "room_status": "BLOCKED",
  "owners": {
    "channel_0": null,
    "channel_1": "hostA_0"
  },
  "publisher_online": {
    "hostA_0": true
  },
  "listener_online": 12,
  "updated_ts": 1710000100
}
```

Rules:
- this file is recoverable snapshot only (source of truth during runtime remains in-memory backend state);
- loaded at startup to restore operational continuity.
- `listener_online` stores current number of opened backend-listener WS sessions.

---

### 17.6 Logs (JSONL event contract)

`connections_log_*.jsonl` line example:
```json
{"ts":1710000110,"timestamp_local":"2024-03-10 02:21:50 +0300","timestamp_utc":"2024-03-09T23:21:50+00:00","event":"publisher_connected","publisher_id":"hostA_0","ip":"10.0.0.12:53321"}
```

`events_log_*.jsonl` line example:
```json
{"ts":1710000120,"timestamp_local":"2024-03-10 02:22:00 +0300","timestamp_utc":"2024-03-09T23:22:00+00:00","event":"on_air_granted","publisher_id":"hostA_0","channel_id":"channel_1","request_id":"onair-req-5"}
```

Mandatory event fields:
- `ts` (unix epoch seconds), `timestamp_local` (local VPS time in `YYYY-MM-DD HH:MM:SS +ZZZZ` format), `timestamp_utc` (UTC ISO timestamp without milliseconds), `event`, `request_id` (if WS-linked), `actor_id`/`client_id` when applicable.

---

### 17.7 Retention and rotation

Baseline policy (MVP):
- rotate JSONL daily (UTC).
- keep hot logs locally 14 days.
- optional archive/export by operator.
- if disk free space < 15%: emit critical warning; if < 10%: stop new recordings before state/log writes fail.

---

### 17.8 Startup recovery order

1) if `room_config_v1.json` exists -> load last imported room metadata;
2) if `room_config_v1.json` does not exist (clean deploy) -> apply immutable bootstrap defaults and persist new `room_config_v1.json`;
3) load `runtime_state_v1.json` (if exists)
4) rebuild in-memory state (channels, room name from i18n `en`, pin, target_capacity)
5) open new JSONL log files for current day
6) append `backend_started` event

Import replacement rule:
- on each successful JSON import backend fully replaces room metadata snapshot (`room_config_v1.json`) and resets runtime metadata that can mix with old room config (owners/recording state).
- backend does not merge old and new channel metadata or retain the previous `subsite_name`; absent/null means no alias.

---

### 17.9 Restart policy (operator expected behavior)

Expected behavior:
1) open backend;
2) backend runs with last imported room metadata; if there was no successful import yet, backend runs with immutable bootstrap defaults;
3) backend can replace room metadata by new admin JSON import.

This policy protects room metadata from emergency VPS reboot data loss.
