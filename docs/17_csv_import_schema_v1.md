## 18. CSV import schema v1 (admin initial room data + i18n library)

Goal:
- formalize Stage VII admin import format;
- prevent partial/ambiguous room setup;
- include immutable deploy-time i18n library bootstrap data;
- provide deterministic validation and error reporting.

---

### 18.1 File format

- Encoding: UTF-8 (BOM allowed, backend reads `utf-8-sig`).
- Delimiter: semicolon `;`.
- Quote char: `"` (RFC4180 compatible).
- First row: header required.
- Line ending: LF or CRLF allowed.

---

### 18.2 Required headers (all required)

```text
channel_id;channel_label;listen;pin;target_capacity;room_name_i18n_en;room_name_i18n_ru;custom_status_text_blocked_i18n_en;custom_status_text_blocked_i18n_ru;custom_status_text_closed_i18n_en;custom_status_text_closed_i18n_ru
```

Rule:
- every header above MUST exist in import file;
- no optional headers in MVP profile;
- unknown headers are rejected.

---

### 18.3 Field rules

`channel_id`:
- required
- expected format: `channel_<number>`
- unique per file

`channel_label`:
- required
- 1..80 chars
- UTF-8 text allowed

`listen`:
- required
- allowed values: `true`, `false` (lowercase)

`pin` (room-level):
- required
- must be identical in all rows

`target_capacity` (room-level):
- required
- positive integer
- must be identical in all rows
- imported as immutable event runtime parameter

i18n room/status fields (room-level):
- `room_name_i18n_en` required, identical in all rows
- `room_name_i18n_ru` required, identical in all rows
- `custom_status_text_blocked_i18n_en` required, identical in all rows
- `custom_status_text_blocked_i18n_ru` required, identical in all rows
- `custom_status_text_closed_i18n_en` required, identical in all rows
- `custom_status_text_closed_i18n_ru` required, identical in all rows

MVP language rule:
- backend imports and sends full immutable `i18n_library` to clients;
- backend does not store per-user `ui_lang` and does not choose language for listener.

---

### 18.4 Validation and apply strategy (baseline)

Process:
1) parse and validate all rows first;
2) if critical error exists -> reject import and show report;
3) if valid -> write new `room_config_v1.json` atomically;
4) compute and persist derived backend limits from `target_capacity`:
   - `max_active_listeners = target_capacity * 1.05`
   - `max_new_connections_per_sec = target_capacity / 15`
5) apply immutable `i18n_library` values from CSV as deploy/runtime dictionaries;
6) emit `csv_import_applied` event to events log.

---

### 18.5 Valid full CSV example

```csv
channel_id;channel_label;listen;pin;target_capacity;room_name_i18n_en;room_name_i18n_ru;custom_status_text_blocked_i18n_en;custom_status_text_blocked_i18n_ru;custom_status_text_closed_i18n_en;custom_status_text_closed_i18n_ru
channel_0;Original - FLOOR - Оригинал;false;123456;200;Conference room;Зал конференции;Stream temporarily stopped;Трансляция временно остановлена;The conference is over. Thank you for your participation;Конференция окончена. Благодарим за участие
channel_1;Russian - RUS - Русский;true;123456;200;Conference room;Зал конференции;Stream temporarily stopped;Трансляция временно остановлена;The conference is over. Thank you for your participation;Конференция окончена. Благодарим за участие
channel_2;English - ENG - English;true;123456;200;Conference room;Зал конференции;Stream temporarily stopped;Трансляция временно остановлена;The conference is over. Thank you for your participation;Конференция окончена. Благодарим за участие
```

---

### 18.6 Invalid CSV example and expected error

Invalid CSV (missing required header `room_name_i18n_ru`):

```csv
channel_id;channel_label;listen;pin;target_capacity;room_name_i18n_en;custom_status_text_blocked_i18n_en;custom_status_text_blocked_i18n_ru;custom_status_text_closed_i18n_en;custom_status_text_closed_i18n_ru
channel_0;Floor;false;123456;200;Conference room;Blocked;Заблокировано;Closed;Закрыто
```

Expected validation response (example):

```json
{
  "ok": false,
  "errors": [
    {
      "line": 1,
      "field": "room_name_i18n_ru",
      "code": "MISSING_HEADER",
      "message": "Header room_name_i18n_ru is required"
    }
  ]
}
```

---

### 18.7 Error codes (baseline)

- `MISSING_HEADER`
- `UNKNOWN_HEADER`
- `INVALID_ENCODING`
- `INVALID_CHANNEL_ID`
- `DUPLICATE_CHANNEL_ID`
- `EMPTY_CHANNEL_LABEL`
- `INVALID_LISTEN_VALUE`
- `INCONSISTENT_ROOM_NAME`
- `INCONSISTENT_PIN`
- `MISSING_TARGET_CAPACITY`
- `INVALID_TARGET_CAPACITY`

---

### 18.8 Operator UX requirements

- show line number + field + human-readable message;
- provide downloadable error report (`.json`);
- require explicit confirmation before replacing active config.
