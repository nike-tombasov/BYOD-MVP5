## 9. Backend - FastAPI

This document follows canonical WS protocol: `docs/15_ws_schema_v1.md`.
If any mismatch appears, `docs/15_ws_schema_v1.md` wins.

### 9.1 Canonical WS scope

Backend accepts/sends only schema v1 envelope messages.

Publisher -> Backend:
- `connecting`
- `heartbeat`
- `on_air`
- `stop`

Backend -> Publisher:
- `connecting`
- `publisher_state`
- `i18n_library`
- `error`

Listener -> Backend:
- `connecting`
- `heartbeat`

Backend -> Listener:
- `connecting`
- `listener_state`
- `i18n_library`
- `error`

Forbidden:
- legacy protocol
- `type: "state"`
- `type: "connected"`
- top-level fields outside `payload`

### 9.2 Handshake order

Publisher:
1) receive `connecting` request;
2) send `connecting` success;
3) send `i18n_library`;
4) send `publisher_state`.

Listener:
1) receive `connecting` request;
2) send `connecting` success;
3) send `i18n_library`;
4) send `listener_state`.

### 9.3 State payload split

`publisher_state.payload`:
- `room_status`
- `channels[]` with `channel_id`, `channel_label`, `owner`, `listen`

`listener_state.payload`:
- `room_status`
- `channels[]` with `channel_id`, `channel_label`, `listen`

### 9.4 i18n policy

`i18n_library`:
- set on deploy/import;
- immutable during event runtime;
- sent once on connect/reconnect;
- contains room/status dictionaries for UI rendering.

### 9.5 Core backend rules (kept)

- Backend is source of truth for ownership/interlock.
- Interlock owner rules are atomic.
- Invalid schema => `error` with `SCHEMA_VALIDATION_ERROR`.
- No WS send while state lock is held.
