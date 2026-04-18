## 10. Listener Web UI

This document follows canonical WS protocol: `docs/15_ws_schema_v1.md`.
If any mismatch appears, `docs/15_ws_schema_v1.md` wins.

### 10.1 Listener WS contract

Listener sends only:
- `connecting`
- `heartbeat`

Listener accepts only:
- `connecting`
- `i18n_library`
- `listener_state`
- `error`

No legacy support:
- no `connected`
- no `state`
- no mixed-format parsing

### 10.2 Listener handshake order (strict)

1) open `/ws/listener`
2) send `connecting`
3) receive `connecting` success (`ok=true`, `listener_id`, `token`, `livekit_url`)
4) receive `i18n_library`
5) receive `listener_state`
6) connect LiveKit
7) render UI

### 10.3 Listener state and UI rendering

`listener_state.payload` contains only:
- `room_status`
- `channels[]` (`channel_id`, `channel_label`, `listen`)

UI rule:
- `OPENED`: hide status banner;
- `BLOCKED`: show `i18n_library.custom_status_text_blocked_i18n`;
- `CLOSED`: show `i18n_library.custom_status_text_closed_i18n`.

No runtime text mutation.

### 10.4 i18n rule

- `i18n_library` is immutable payload from backend.
- Listener chooses language locally: exact -> base -> `en`.
- Language detection happens at page start.

### 10.5 Audio control rules

- selective subscribe only;
- one selected channel at a time;
- `BLOCKED`: stop audio immediately, buttons clickable;
- `CLOSED`: stop audio, clear selected channel, lock controls;
- `OPENED` after `BLOCKED`: resume selected channel without page reload.
