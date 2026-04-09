## 16. WebSocket schema v1 (Publisher/Listener/Backend)

Purpose:
- define strict JSON contract for all WS interactions;
- prevent drift between backend, Publisher and Listener implementations;
- provide deterministic validation / retry / compatibility behavior.

Scope:
- Backend <-> Publisher WS
- Backend <-> Listener WS
- does not replace LiveKit media signaling; applies only to application WS messages.

---

### 16.1. General envelope (all WS messages)

Every WS message MUST be a JSON object:

```json
{
  "type": "string",
  "schema_version": 1,
  "ts": 1710000000,
  "request_id": "uuid-or-client-generated-id",
  "payload": {}
}
```

Fields:
- `type` (required, string): message type identifier.
- `schema_version` (required, integer): schema version for this message family.
- `ts` (required, integer): unix timestamp (seconds), sender local time.
- `request_id` (required, string): id for correlation and idempotency.
- `payload` (required, object): message-specific body.

Validation rule:
- unknown top-level fields are allowed only if backward compatible and ignored by receiver;
- missing required fields => protocol error.

---

### 16.2. Message families

Backend <-> Publisher:
- `connecting`
- `heartbeat`
- `on_air`
- `stop`
- `publisher_state`
- `error`

Backend <-> Listener:
- `connecting`
- `heartbeat`
- `listener_state`
- `i18n_library`
- `error`

---

### 16.3. `connecting`

#### 16.3.1 Publisher -> Backend

```json
{
  "type": "connecting",
  "schema_version": 1,
  "ts": 1710000000,
  "request_id": "pub-req-1",
  "payload": {
    "client_role": "publisher",
    "pin": "123456",
    "hostname": "PC-01"
  }
}
```

Required payload fields:
- `client_role` = `publisher`
- `pin` (string)
- `hostname` (string)

#### 16.3.2 Listener -> Backend

```json
{
  "type": "connecting",
  "schema_version": 1,
  "ts": 1710000001,
  "request_id": "lst-req-1",
  "payload": {
    "client_role": "listener"
  }
}
```

Required payload fields:
- `client_role` = `listener`

#### 16.3.3 Backend -> client (success response)

```json
{
  "type": "connecting",
  "schema_version": 1,
  "ts": 1710000002,
  "request_id": "pub-req-1",
  "payload": {
    "ok": true,
    "client_role": "publisher",
    "publisher_id": "hostA_0",
    "token": "<jwt>",
    "livekit_url": "wss://lk.example.com",
    "room_name": "Room A",
    "room_status": "OPENED"
  }
}
```

For listener response:
- `client_role` = `listener`
- `listener_id` вместо `publisher_id`
- `token`, `livekit_url`, `room_status` required.

Backend MUST send `i18n_library` after successful connect for both client roles.

---

### 16.4. `heartbeat`

```json
{
  "type": "heartbeat",
  "schema_version": 1,
  "ts": 1710000100,
  "request_id": "hb-1",
  "payload": {
    "client_role": "listener",
    "client_id": "listener_12",
    "play_active": true
  }
}
```

Rules:
- Publisher heartbeats: `play_active` may be omitted.
- Listener heartbeats: when active PLAY, send every 10 sec (MVP baseline).
- heartbeat timeout behavior follows backend policy (60 sec for active PLAY).
- when listener returns from background with no active PLAY and stale WS session, client should auto-reconnect (or auto-reload fallback).
- listener client connection state machine (`CONNECTED`/`STALE`/`RECONNECTING`) is defined in `docs/09_listener_ui.md` section 10.10.1.

---

### 16.5. `on_air` (Publisher -> Backend)

```json
{
  "type": "on_air",
  "schema_version": 1,
  "ts": 1710000200,
  "request_id": "onair-req-5",
  "payload": {
    "publisher_id": "hostA_0",
    "channel_id": "channel_2",
    "request_on_air_ts": 1710000199
  }
}
```

Required:
- `publisher_id`, `channel_id`, `request_on_air_ts`.

Idempotency:
- duplicate same-owner request MAY be accepted as no-op.

---

### 16.6. `stop` (Publisher -> Backend)

```json
{
  "type": "stop",
  "schema_version": 1,
  "ts": 1710000300,
  "request_id": "stop-req-2",
  "payload": {
    "publisher_id": "hostA_0",
    "channel_id": "channel_2",
    "request_off_air_ts": 1710000299
  }
}
```

Required:
- `publisher_id`, `channel_id`, `request_off_air_ts`.

---

### 16.7. `publisher_state` (Backend -> Publisher)

```json
{
  "type": "publisher_state",
  "schema_version": 1,
  "ts": 1710000400,
  "request_id": "state-100",
  "payload": {
    "room_name": "Room A",
    "room_status": "OPENED",
    "channels": [
      {
        "channel_id": "channel_0",
        "channel_label": "Floor",
        "owner": null,
        "listen": false
      }
    ]
  }
}
```

---

### 16.8. `listener_state` (Backend -> Listener)

```json
{
  "type": "listener_state",
  "schema_version": 1,
  "ts": 1710000401,
  "request_id": "state-101",
  "payload": {
    "room_status": "OPENED",
    "channels": [
      {
        "channel_id": "channel_1",
        "channel_label": "English",
        "listen": true
      }
    ]
  }
}
```

Notes:
- `owner` is intentionally excluded from Listener state.
- i18n maps are not repeated in each `listener_state`; they are delivered via `i18n_library`.

---

### 16.9. `i18n_library` (Backend -> Publisher and Listener)

Sent on:
- initial connect success
- reconnect success
- emergency override update/reset events (same message type, updated payload)

```json
{
  "type": "i18n_library",
  "schema_version": 1,
  "ts": 1710000402,
  "request_id": "i18n-1",
  "payload": {
    "library_version": 1,
    "room_name_i18n": {
      "en": "Room A",
      "ru": "Зал А"
    },
    "custom_status_text_blocked_i18n": {
      "en": "Temporarily blocked",
      "ru": "Временно заблокировано"
    },
    "custom_status_text_closed_i18n": {
      "en": "Room is closed",
      "ru": "Зал закрыт"
    }
  }
}
```

Rules:
- base deploy dictionaries are immutable during event runtime;
- emergency override modifies runtime payload only (in-memory backend override);
- Publisher receives full library but renders `en` in MVP;
- Listener performs language detection and local fallback (`exact tag -> base tag -> en`).

---

### 16.10. `error` (Backend -> any client)

```json
{
  "type": "error",
  "schema_version": 1,
  "ts": 1710000500,
  "request_id": "onair-req-5",
  "payload": {
    "code": "ON_AIR_REJECTED_OWNER_MISMATCH",
    "message": "channel owner is another publisher",
    "retryable": false
  }
}
```

Core error codes:
- `INVALID_PIN`
- `UNAUTHORIZED`
- `SCHEMA_VALIDATION_ERROR`
- `ON_AIR_REJECTED_OWNER_MISMATCH`
- `CHANNEL_NOT_FOUND`
- `RATE_LIMITED`
- `INTERNAL_ERROR`
- `RECONNECT_REQUIRED`

Retry baseline:
- retryable=false: do not auto-retry (show operator/user state).
- retryable=true: exponential backoff (`1s, 2s, 4s`, cap `10s`, jitter).

---

### 16.11. Concurrency and ordering constraints

- Backend must use snapshot-send pattern:
  - lock state
  - copy immutable snapshot
  - unlock
  - send snapshot
- sending while holding lock is forbidden.
- Clients must ignore stale state by comparing `ts` and local monotonic order.

---

### 16.12. Compatibility policy

- `schema_version` for `publisher_state` and `listener_state` may evolve independently.
- backward-compatible additions:
  - new optional fields allowed;
  - unknown optional fields ignored by receivers.
- breaking changes:
  - require new `schema_version`;
  - require acceptance checklist update before rollout.

---

### 16.13. Validation checklist (minimum)

Before stage completion:
1) connect/reconnect success for Publisher and Listener;
2) `i18n_library` delivered to both client roles on connect/reconnect;
3) `publisher_state` / `listener_state` pass required-field validation;
4) error codes are deterministic for invalid PIN / owner mismatch / schema error;
5) no state lock held during send operations;
6) rapid reconnects do not break schema processing.

---

### 16.14. Deferred advanced protocol topics (not blocking Stage VII-IX)

Moved to later stages / future features:
- WS ACK/NACK flow;
- request_id deduplication cache;
- reconnect session resume;
- advanced retry policies and close-code strategy.
