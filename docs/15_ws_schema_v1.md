## 16. WebSocket schema v1 (canonical)

This is the **single canonical WS protocol** for all nodes:
- Backend
- Publisher
- Listener

No legacy protocol is allowed.
No `type: "state"`.
No `type: "connected"`.
No top-level payload fields outside `payload`.

---

### 16.1 Common envelope (mandatory for every WS message)

Every message MUST be:

```json
{
  "type": "string",
  "schema_version": 1,
  "ts": 1710000000,
  "request_id": "string",
  "payload": {}
}
```

Required fields:
- `type`
- `schema_version`
- `ts`
- `request_id`
- `payload`

Rules:
- `schema_version` MUST be `1`.
- Missing required field => protocol error.
- Old formats are forbidden.

---

### 16.2 Allowed message types (final set)

Publisher -> Backend:
- `connecting`
- `heartbeat`
- `on_air`
- `stop`

Backend -> Publisher:
- `connecting` (success response)
- `publisher_state`
- `i18n_library`
- `error`

Listener -> Backend:
- `connecting`
- `heartbeat`

Backend -> Listener:
- `connecting` (success response)
- `listener_state`
- `i18n_library`
- `error`

---

### 16.3 Handshake order (strict)

#### Listener handshake
1) Listener opens `/ws/listener`.
2) Listener sends `connecting`.
3) Backend sends `connecting` success (`ok=true`, `listener_id`, `token`, `livekit_url`).
4) Backend sends `i18n_library`.
5) Backend sends `listener_state`.
6) Listener connects to LiveKit.
7) Listener renders UI.

#### Publisher handshake
1) Publisher opens `/ws/publisher`.
2) Publisher sends `connecting` with `pin`, `hostname`.
3) Backend sends `connecting` success (`ok=true`, `publisher_id`, `token`, `livekit_url`).
4) Backend sends `i18n_library`.
5) Backend sends `publisher_state`.

---

### 16.4 `connecting`

Listener request payload:
```json
{
  "client_role": "listener"
}
```

Publisher request payload:
```json
{
  "client_role": "publisher",
  "pin": "123456",
  "hostname": "PC-01"
}
```

Success response payload:
- Common required fields:
  - `ok: true`
  - `client_role`
  - `token`
  - `livekit_url`
- For Publisher:
  - `publisher_id`
- For Listener:
  - `listener_id`

---

### 16.5 `publisher_state`

`publisher_state.payload` contains only:
- `room_status`
- `channels`

`channels[]` for Publisher contains only:
- `channel_id`
- `channel_label`
- `owner`
- `listen`

---

### 16.6 `listener_state`

`listener_state.payload` contains only:
- `room_status`
- `channels`

`channels[]` for Listener contains only:
- `channel_id`
- `channel_label`
- `listen`

Must NOT contain:
- `owner`
- i18n maps
- legacy wrappers

---

### 16.7 `i18n_library`

`i18n_library` is immutable runtime payload.
It is set at deploy/import time.
It is sent on connect/reconnect.
It is not changed during event runtime.

Required maps:
- `room_name_i18n`
- `custom_status_text_blocked_i18n`
- `custom_status_text_closed_i18n`

`listener_state` and `publisher_state` do not include i18n maps.

---

### 16.8 `heartbeat`

Allowed for both clients.
Envelope is required.

---

### 16.9 `on_air` / `stop`

Publisher only.
Envelope is required.

Forced channel release rule:
- no `force_off_air` WS message exists;
- backend performs forced release as state transition only:
  - set channel `owner = null`
  - broadcast normal `publisher_state`
- Publisher reacts only to `publisher_state` and stops local streaming when owner is no longer equal to own `publisher_id`;
- Listener is not involved in forced off-air logic.

---

### 16.10 `error`

Backend may send `error` for protocol/schema/business failures.

Baseline codes:
- `SCHEMA_VALIDATION_ERROR`
- `INVALID_PIN`
- `NOT_CONNECTED`
- `UNKNOWN_CHANNEL`
- `OWNER_MISMATCH`
- `RECONNECT_TOO_FAST`
- `LISTENER_OVERFLOW`
- `CONNECTION_RATE_LIMIT`

---

### 16.11 Hard ban of old formats

Explicitly forbidden:
- messages without `schema_version`
- top-level fields instead of `payload`
- `type: "state"`
- `type: "connected"`

Clients do not support old messages.
Any old message is protocol error.
