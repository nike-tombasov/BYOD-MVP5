## 18. JSON import schema v1 (admin room config + i18n library)

Goal:
- replace old rigid import approach with scalable JSON import;
- support arbitrary language tags in immutable `i18n_library`;
- keep MVP language model unchanged.

---

### 18.1 File format

- Encoding: UTF-8 (`utf-8-sig` accepted).
- Payload root: JSON object.
- Unicode text is fully supported.

Canonical admin endpoint:
- `POST /admin/import_json`

---

### 18.2 Required top-level fields

```json
{
  "pin": "123456",
  "subsite_name": "test-conf",
  "target_capacity": 200,
  "channels": [],
  "i18n_library": {}
}
```

`pin`, `target_capacity`, `channels`, and `i18n_library` are required. `subsite_name` is optional.

---

### 18.3 Validation rules

Top-level:
- `pin`: non-empty string
- `target_capacity`: positive integer
- `channels`: non-empty list
- `i18n_library`: object


`subsite_name` rules:
- optional top-level field; absent, `null`, an empty string, or a whitespace-only string means no alias;
- a non-empty value is trimmed and must be one lowercase ASCII URL path slug matching `^[a-z0-9][a-z0-9_-]{0,63}$`;
- slash, dot, colon, spaces, uppercase, Unicode, `%`, `?`, `#`, and backslash are not allowed;
- reserved values `admin`, `health`, `ws`, `listener.js`, `vendor`, `index.html`, and `favicon.ico` are rejected;
- `"subsite_name": "test-conf"` enables the Listener path `/test-conf/`; Listener root `/` remains valid;
- the slug is a URL path, not DNS, and creates neither additional LiveKit rooms nor multiple simultaneous events on one VPS;
- each successful import replaces the previous alias rather than merging with it.

`channels` item rules:
- each item must be object with required fields:
  - `channel_id`
  - `channel_label`
  - `listen`
- `channel_id` format: `channel_<number>`
- channel ids must be unique
- `channel_label` must be non-empty string
- `listen` must be boolean

`i18n_library` required maps:
- `room_name_i18n`
- `custom_status_text_blocked_i18n`
- `custom_status_text_closed_i18n`

Each map must be object of `{language_tag: text}`:
- language tags are not hardcoded to only `en`/`ru`;
- additional tags are accepted (`zh`, `zh-CN`, `ar`, etc.);
- MVP still requires at least `en` and `ru` in each map;
- all map values must be non-empty strings.

MVP rule unchanged:
- backend imports and sends full immutable `i18n_library`;
- backend does not store per-user `ui_lang`;
- backend does not choose language per listener.

---

### 18.4 Apply strategy

Process:
1) parse JSON and validate full payload;
2) if any critical error -> reject import;
3) if valid -> fully replace room metadata snapshot atomically;
4) reset runtime metadata that can mix with old channel set (owners/recording markers);
5) compute derived limits:
   - `max_active_listeners = target_capacity * 1.05`
   - `max_new_connections_per_sec = target_capacity / 15`
6) persist full `i18n_library` without dropping extra languages;
7) emit `json_import_applied` event.

---

### 18.5 Valid JSON example (with extra `zh` language)

```json
{
  "pin": "123456",
  "subsite_name": "test-conf",
  "target_capacity": 200,
  "channels": [
    {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": false},
    {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": true},
    {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": true}
  ],
  "i18n_library": {
    "room_name_i18n": {
      "en": "Conference room",
      "ru": "Зал конференции",
      "zh": "会议厅"
    },
    "custom_status_text_blocked_i18n": {
      "en": "Stream temporarily stopped",
      "ru": "Трансляция временно остановлена",
      "zh": "传输暂时停止"
    },
    "custom_status_text_closed_i18n": {
      "en": "The conference is over. Thank you for your participation",
      "ru": "Конференция окончена. Благодарим за участие",
      "zh": "会议结束，感谢您的参与"
    }
  }
}
```

---

### 18.6 Invalid JSON example and expected error

Invalid example (invalid `subsite_name` and missing `ru` in `room_name_i18n`):

```json
{
  "pin": "123456",
  "subsite_name": "Old/Event",
  "target_capacity": 200,
  "channels": [
    {"channel_id": "channel_0", "channel_label": "Floor", "listen": false}
  ],
  "i18n_library": {
    "room_name_i18n": {"en": "Conference room"},
    "custom_status_text_blocked_i18n": {"en": "Blocked", "ru": "Заблокировано"},
    "custom_status_text_closed_i18n": {"en": "Closed", "ru": "Закрыто"}
  }
}
```

Expected validation error example:

```json
{
  "ok": false,
  "errors": [
    {
      "line": 1,
      "field": "subsite_name",
      "code": "INVALID_SUBSITE_NAME",
      "message": "subsite_name must match ^[a-z0-9][a-z0-9_-]{0,63}$"
    },
    {
      "line": 1,
      "field": "room_name_i18n.ru",
      "code": "MISSING_REQUIRED_LANG",
      "message": "room_name_i18n must include non-empty ru"
    }
  ]
}
```

---

### 18.7 Error codes (baseline)

- `INVALID_ENCODING`
- `INVALID_JSON`
- `MISSING_FIELD`
- `INVALID_PIN`
- `INVALID_SUBSITE_NAME`
- `RESERVED_SUBSITE_NAME`
- `INVALID_TARGET_CAPACITY`
- `INVALID_CHANNELS`
- `INVALID_CHANNEL`
- `INVALID_CHANNEL_ID`
- `DUPLICATE_CHANNEL_ID`
- `EMPTY_CHANNEL_LABEL`
- `INVALID_LISTEN_VALUE`
- `INVALID_I18N_LIBRARY`
- `INVALID_I18N_MAP`
- `MISSING_REQUIRED_LANG`
- `INVALID_LANGUAGE_TAG`
- `INVALID_I18N_TEXT`
