## 8. Publisher UI

This document follows canonical WS protocol: `docs/15_ws_schema_v1.md`.
If any mismatch appears, `docs/15_ws_schema_v1.md` wins.

### 8.1 Publisher WS contract

Publisher sends only:
- `connecting`
- `heartbeat`
- `on_air`
- `stop`

Publisher accepts only:
- `connecting`
- `publisher_state`
- `i18n_library`
- `error`

No legacy support:
- no `connected`
- no `state`
- no top-level payload shortcuts

### 8.2 Publisher handshake order (strict)

1) open `/ws/publisher`
2) send `connecting` with `pin`, `hostname`
3) receive `connecting` success (`ok=true`, `publisher_id`, `token`, `livekit_url`)
4) receive `i18n_library`
5) receive `publisher_state`

### 8.3 Publisher state usage

`publisher_state.payload` contains:
- `room_status`
- `channels[]` with `channel_id`, `channel_label`, `owner`, `listen`

Publisher uses `owner` for interlock.
Listener does not use `owner`.

### 8.4 i18n rule

- `i18n_library` is immutable for event runtime;
- Publisher receives it after connect/reconnect;
- Publisher MVP UI renders `en` texts.
