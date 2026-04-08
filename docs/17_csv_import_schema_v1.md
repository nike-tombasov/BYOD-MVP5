## 18. CSV import schema v1 (admin initial room data)

Goal:
- formalize Stage VII admin import format;
- prevent partial/ambiguous room setup;
- provide deterministic validation and error reporting.

---

### 18.1 File format

- Encoding: UTF-8 (without BOM preferred).
- Delimiter: comma `,`.
- Quote char: `"` (RFC4180 compatible).
- First row: header required.
- Line ending: LF or CRLF allowed.

---

### 18.2 Required headers

```text
channel_id,channel_label,listen
```

Optional headers:
- `room_name` (if repeated in each row, values must be identical)
- `pin` (if repeated in each row, values must be identical)

If optional headers are omitted, room-level values are taken from operator input or existing persisted config.

---

### 18.3 Field rules

`channel_id`:
- required
- regex: `^channel_([0-9]|[1-2][0-9]|3[0-1])$`
- unique per file

`channel_label`:
- required
- 1..80 chars
- UTF-8 text allowed

`listen`:
- required
- allowed values: `true`, `false` (lowercase)

Additional rule:
- `channel_0` may be imported as `listen=false` by default; if imported as true, operator confirmation is required before applying.

---

### 18.4 Example CSV

```csv
channel_id,channel_label,listen,room_name,pin
channel_0,Floor,false,Main Hall,123456
channel_1,English,true,Main Hall,123456
channel_2,German,true,Main Hall,123456
```

---

### 18.5 Validation and apply strategy

Process:
1) parse and validate all rows first;
2) if any error exists -> reject full file (no partial apply);
3) if valid -> write new `room_config_v1.json` atomically;
4) emit `csv_import_applied` event to events log.

Error payload example:
```json
{
  "ok": false,
  "errors": [
    {"line": 3, "field": "channel_id", "code": "DUPLICATE_CHANNEL_ID", "message": "channel_1 already used"}
  ]
}
```

---

### 18.6 Error codes

- `MISSING_HEADER`
- `UNKNOWN_HEADER`
- `INVALID_ENCODING`
- `INVALID_CHANNEL_ID`
- `DUPLICATE_CHANNEL_ID`
- `EMPTY_CHANNEL_LABEL`
- `INVALID_LISTEN_VALUE`
- `INCONSISTENT_ROOM_NAME`
- `INCONSISTENT_PIN`

---

### 18.7 Operator UX requirements

- show line number + field + human-readable message;
- provide downloadable error report (`.json`);
- require explicit confirmation before replacing active config.
