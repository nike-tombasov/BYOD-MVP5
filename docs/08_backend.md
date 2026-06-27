## 9. Backend - FastAPI

WS wire-protocol canonical source: `docs/15_ws_schema_v1.md`.
This file describes backend semantics/operations and must not conflict with canonical wire schema.

pip install fastapi uvicorn websockets pyjwt livekit-api

### 9.1. Содержание базы данных Backend, управляемых admin

Persistence formalization:
- canonical file for storage layout and atomic write rules: `docs/16_backend_persistence_json_v1.md`.
- canonical file for admin JSON import format and validation: `docs/17_json_import_schema_v1.md`.

Startup/import persistence policy:
- after restart backend must keep last successful imported room metadata;
- only clean deploy (no import yet) uses immutable bootstrap defaults;
- each new successful JSON import fully replaces previous room metadata snapshot (no metadata mixing).

1) room PIN (6-тизначный код)
2) channel number - channel_id по форме channel_0, channel_1, channel_2...
3) channel name - channel_label для каждого channel_id - не используется в SFU WebRTC и требуется только для визуального отображения в UI
4) режим прослушивания channel - listen (false - по умолчанию для channel_0, Reserve 1 и Reserve 2, и true - по умолчанию для всех остальных) - для каждого channel_id
5) room name - room_name
6) room status - room_status (BLOCKED по умолчанию при clean deploy до первого импорта)
7) status custom text - текст для web page на room statuses BLOCKED и CLOSED
8) target_capacity - целевое количество Listener для sizing/лимитов VPS (задаётся при deploy и не изменяется в runtime мероприятия)

### 9.2. Tokens and PIN

JWT tokens выдаются на основе Identity и разные для Listener и Publisher.

Current timeout policy (MVP):
- JWT lifetime = **2 hours**.

Refresh policy (single source of truth):
- Publisher: refresh token за 10 минут до expiry.
- Listener: новый token запрашивается только при reconnect необходимости.

Infrastructure requirement:
- VPS time sync (NTP) is mandatory to keep JWT expiry/refresh timings stable.

JWT token содержит:
* room
* identity
* permissions

1) При подключении LiveKit Identity - listener выдаётся token Identity listener_id. Никакой верификации не требуется.
2) При подключении LiveKit Identity - publisher выдаётся token Identity publisher_id только после проверки PIN.

PIN устанавливается admin в момент разворачивания сервера VPS. Может быть изменён в любое время.
При ручном изменении PIN все Publisher со статусом online не прекращают свою работу. Новый PIN потребуется room technician только для нового подключения. CONNECT к backend по старому PIN с этого момента невозможен.

LiveKit API credentials policy:
* LiveKit API key/secret генерируются автоматически во время VPS deploy.
* `LIVEKIT_API_SECRET` для production deploy: длина строго `> 32` символов.
* Секрет сохраняется синхронно в backend env/config и `livekit.yaml` конкретного VPS deploy.
* Запрещено хранить production secret в git-репозитории.

### 9.3. Room status (room_status)

Admin изменяет room status вручную. Room status не приостанавливает streaming, publishing, sending frames и никак не влияет на interlock owner-логику Publisher.

* OPENED — listener может получать звук по canonical listener rules.
* BLOCKED — listener не получает звук; показывается `custom_status_text_blocked`.
* CLOSED — listener не получает звук; показывается `custom_status_text_closed`.

Recording clarification for current MVP baseline:
- real backend multitrack recording is **not implemented** in current MVP baseline;
- backend currently keeps only recording state markers/runtime control placeholders.
- real recording implementation is moved to future features after MVP pilots.

### 9.4. Регистрация подключений

Каждый подключающийся Publisher после верификации по PIN должен быть занесён в базу данных по следующим полям (минимально):
- hostname (system Windows)
- publisher_counter (счётчик начиная с 0, если Publisher вдруг переподключился - это уже новая регистрация с следующим по порядку номером счётчика)
- publisher_id (hostname+counter, например, hostPCname_0)
- publisher_connection_ts (время подключения) 
- publisher_online (true/false)
- last_seen_ts (время последнего heartbeat в статусе publisher_online  true)
- publisher_ip (адрес и порт подключения)

Эти данные служат для управления логикой interlock при multi-publisher connections, а также для statistics.

Каждый подключающийся listener должен быть занесён в базу данных по следующим полям (минимально):
- listener_counter (счётчик начиная с 0)
- listener_id (например, listener_0)
- listener_connection_ts (время подключения) 
- listener_ip (адрес и порт подключения)

Эти данные служат для выдачи JWT tokens, управления логикой interlock при multi-publisher connections, а также для statistics.

### 9.5. Регистрация ON AIR

Хранение по каждому из channel_id в базе данных:
- owner - publisher_id, нажавший ON AIR button первым согласно timestamp (null, если не было нажатий ON AIR или если owner нажал STOP)
- channel_on_air - on air / free
- on_air_ts - время последнего изменения owner при ON AIR
- off_air_ts - время последнего изменения owner при STOP или потери связи с owner

request_on_air_ts и request_off_air_ts не используется в управлении, хранится в backend только для логирования.

Idempotency rule:
```
if owner == null:
    set owner
elif owner == same publisher:
    ignore duplicate ON AIR
else:
    reject ON AIR
```

### 9.6. Interlock логика

Защититься от гонок (atomic updates). 
Лимитировать давность поступившего запроса в 30 секунд при расхождение request on air timestamp от current time на случай зависания Publisher или обрывов интернет соединения (ввиду потенциальной неактуальности, чтобы не оборвать актуальный Publisher).
Первый Publisher, чей запрос ON AIR первым атомарно зафиксирован backend server time, становится owner. request_on_air_ts от Publisher хранится только для логов и не используется для выбора owner (чтобы избежать ошибок из-за рассинхрона часов на разных PC). Остальные Publishers получат статус ENGAGE, при этом кнопка ON AIR станет не активна вплоть до смены owner на null.

Наличие тишины в channel не является браком в момент переключений, когда один Publisher STOP (unpublish), а второй Publisher ON AIR (publish).

Примерная схема при ON AIR:

publisher presses ON_AIR 
↓
backend receives request
↓
backend sets owner(channel_id)
↓
backend sets channel_on_air(channel_id) = on_air
↓
backend broadcasts `publisher_state`
↓
publishers update UI 
↓
owner publisher start streaming
↓
owner publisher sets UI channel status STREAMING
↓
non-owner publishers sets UI channel status ENGAGED

Похожая схема и при STOP:

publisher presses STOP (streaming stopping, unpublish)
↓
owner publisher sets UI channel status Connecting...
↓
backend receives request
↓
backend sets owner(channel_id) = null
↓
backend sets channel_on_air(channel_id) = free
↓
backend broadcasts `publisher_state`
↓
publishers update UI
↓
publishers sets UI channel status FREE

### 9.7. Взаимодействие с Publisher по WebSocket

1) Publisher/connecting
получает PIN и hostname

- при валидном PIN регистрирует Publisher в базе данных, генерирует и отправляет в ответ JWT token Identity publisher_id и персональный publisher_id, а также room_name, room_status, channel_id, channel_label, owner (по каждому channel_id)
- на initial connect и reconnect дополнительно отправляет `i18n_library` (immutable base dictionaries)
- при невалидном PIN возвращает сигнал об ошибке PIN

2) Регулярный Heartbeats и обновление room_name, room_status, channel_id, channel_label, owner (по каждому channel_id)

3) Publisher/channel on air
получает publisher_id, channel_id, request_on_air_ts

4) Publisher/channel stop  
получает publisher_id, channel_id, request_off_air_ts

5) Publisher/offline  
Если отсутствие heartbeats 30 секунд по этому publisher_id, то в каждом channel_id сменить в owner его publisher_id на null  

Forced OFF AIR policy:
- console command `off_air <channel_id>` performs backend state transition only;
- backend sets `owner = null` and `off_air_ts`, persists state, then broadcasts normal `publisher_state`/`listener_state`;
- backend does not send any extra direct WS command for this flow.

### 9.8. Взаимодействие с Listener по WebSocket

Listener использует WebSocket для:
- channel list (channel_id, channel_label, listen)
- room info (room_name, room_status, status custom text)
- `i18n_library` (room/status texts dictionaries) на initial connect и reconnect

Listener НЕ использует backend state (и в частности owner) для управления аудио.
Аудио управление Listener осуществляется через события LiveKit и channel button condition.

Использовать CORS

### 9.9. Channel multi-track recording (current baseline clarification)

Current MVP baseline:
- backend does **not** create real multitrack audio files yet;
- backend may keep recording state markers/logging only;
- operator commands related to recording affect markers/placeholders, not real file pipeline.

Future feature (after MVP pilots):
- real backend multitrack recording implementation;
- format, bitrate, file naming and lifecycle policy will be finalized in future stages.

### 9.10. Admin Web UI (в будущем)

Доступ на страницу управления только по логину и паролю. Логин и пароль вшивается в deploy, но может быть изменён только при ручном входе на VPS через терминал дата центра, PuTTY или иное.
Возможность объединить управление всеми комнатами (объединение всех VPS в одну локальную сеть дата-центра под одни общим публичным IP), где контроль и управление будет размещено на VPS главного зала конференции с более высокой мощностью.

Admin управляет backend в web UI. Функциональные возможности:

1) начальный ввод room data (PIN, room name, channel number, channel name/label, listen channel_0)
2) пост-управление room data (изменение PIN, room name, channel name/label, режимов listen)
3) изменение room status (OPENED, CLOSED, BLOCKED)
4) визуальный room control - суммарное количество listener (counter), суммарное общее количество subscribed listeners (active  users), длительность статуса OPENED (stopwatch), recording status (on/off)
5) визуальный контроль channels status по каждому channel_id - текущий owner, длительность последнего on_air (stopwatch), количество subscribed listeners (active user), общее количество subscribes (counter)
6) возможность OFF AIR по каждому channel_id(owner == null, рассылка `publisher_state`/`listener_state`)
7) управление recording markers сейчас, и real channel multi-track recording после отдельной future implementation
8) состояние room VPS или всех VPS мероприятия (online, CPU, RAM, SSD, LAN/WAN)
9) визуальный контроль отдельного списка всех Publisher (publisher_id, publisher_online, publisher_connection_ts, last_seen_ts, publisher_ip, number of on air channels)
10) сохранение и download многоуровневой итоговой statistics
11) downloading channel multi-track (интеграция с облачными хранилищами с автоматическим копированием по команде)
*) to be continued…

### 9.11. State (separated)

Backend рассылает **два разных state-сообщения**:

1) `publisher_state`:
- room_name (English)
- room_status
- channels (channel_id, channel_label, owner, listen)

2) `listener_state`:
- room_status
- channels (channel_id, channel_label, listen)

Schema rule:
- `publisher_state` и `listener_state` используют общий envelope schema v1 из `docs/15_ws_schema_v1.md`.

Publisher использует owner для interlock логики.
Listener НЕ использует owner для управления аудио.

### 9.12 WebSocket

Minimal protocol:
* connecting
* heartbeat
* on_air
* stop
* publisher_state
* listener_state

Mandatory backend broadcast concurrency rule:
```
lock state
copy immutable snapshot
unlock state
send snapshot to clients (without lock)
```

Запрещено удерживать state lock во время сетевых send операций.

Formal WS schema requirement:
* отдельный документ контракта обязателен (типы сообщений, обязательные поля, коды ошибок, retry behavior);
* до публикации schema v1 используются временные строгие runtime-валидации и совместимость через acceptance checklist.
* canonical v1 document: `docs/15_ws_schema_v1.md`.

### 9.13. Multi-language data delivery for Publisher and Listener UI (MVP)

Rules:
1) status texts (`custom_status_text_blocked`, `custom_status_text_closed`) и room name фиксируются при deploy и не меняются во время мероприятия;
2) backend отправляет полный набор i18n данных как immutable `i18n_library` при initial WS connect и reconnect **для Listener и Publisher**;
3) backend не получает `ui_lang` и не выбирает язык интерфейса за клиентов;
4) выбор языка выполняет только клиентская сторона (Listener page / Publisher UI rendering policy);
5) i18n maps отправляются на connect/reconnect, не рассылаются в каждый state update;
6) deploy dictionaries immutable during event runtime.

Mandatory dictionaries for each event:
- `en` (required)
- `ru` (required)

Backend payload (образец):
```json
{
  "room_name_i18n": {
    "en": "Test room",
    "ru": "Тестовая комната",
    "zh": "考场"
  },
  "custom_status_text_blocked_i18n": {
    "en": "Temporarily blocked",
    "ru": "Временно заблокировано",
    "zh": "暂时封锁"
  },
  "custom_status_text_closed_i18n": {
    "en": "Room is closed",
    "ru": "Зал закрыт",
    "zh": "会场已关闭"
  }
}
```

Publisher UI receives English texts (`en`) in MVP.
Publisher получает полный `i18n_library`, но в MVP рендерит английский (`en`) как основной UI язык.

JSON must be UTF-8/Unicode safe for Cyrillic, CJK and other language symbols.

i18n/import and persistence consistency note:
- i18n library bootstrap/import format is formalized in:
  - `docs/17_json_import_schema_v1.md` (required JSON fields for channels + i18n library maps);
  - `docs/16_backend_persistence_json_v1.md` (`room_config_v1.json` includes `i18n_library` + deploy immutable defaults before first import).
- MVP rule unchanged: backend sends full immutable `i18n_library`, backend does not store per-user `ui_lang`, backend does not choose language per listener.


### 9.14. Status texts policy

Status texts for BLOCKED/CLOSED come from immutable deploy/import `i18n_library`.
Runtime text mutation is not used in current project.

### 9.15. Protection from unwanted room overflow by Listeners

Backend uses baseline protective limits for Listener admission and room overflow control. В normal event setup
оператор задаёт `target_capacity` в room config JSON; Python constants на VPS
обычно не редактируются. Формулу полезно видеть целиком, но при temporary
stress/emergency tuning менять только финальный override через env/drop-in.

| Variable / value | Meaning |
|---|---|
| `target_capacity` | Normal event sizing from imported room config JSON. Clean deploy/no import uses code fallback `DEFAULT_TARGET_CAPACITY`. |
| `max_active_listeners` | Derived active Listener hard limit; normally `int(target_capacity * 1.05)`. |
| `BYOD_MAX_ACTIVE_LISTENERS_OVERRIDE` | Optional temporary hard override for `max_active_listeners`; normally unset. |
| `max_new_connections_per_sec` | Global backend Listener admission rate, derived from `target_capacity` unless override is set. |
| `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE` | Temporary stress/emergency override for global Listener admission rate; normally unset. |
| `MAX_NEW_CONNECTIONS_PER_SEC_MIN` | Code default minimum in current implementation: `1`. |
| `MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR` | Code default divisor in current implementation: `15.0`. |
| `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` | Per-IP Listener connect/reconnect throttle. Default `2`; set `0` to disable this specific per-IP throttle. |
| `BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED` | Controlled stress/load-test bypass for the per-IP reconnect throttle; not for real production/event traffic. |
| `BYOD_LOADGEN_RECONNECT_BYPASS_KEY` | Shared key required by controlled load generators when bypass is enabled. |

1) Hard limit active listeners:
- `max_active_listeners` is derived from `target_capacity` unless
  `BYOD_MAX_ACTIVE_LISTENERS_OVERRIDE` is set;
- при превышении новых listeners не подключать (возврат отказа подключения).

2) Rate-limit new connections:

```text
max_new_connections_per_sec =
  BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE
  if BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE is set,
  else max(MAX_NEW_CONNECTIONS_PER_SEC_MIN,
           int(target_capacity / MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR))
```

Current defaults:

```text
MAX_NEW_CONNECTIONS_PER_SEC_MIN = 1
MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR = 15.0
```

Normally do not edit the formula. `MAX_NEW_CONNECTIONS_PER_SEC_MIN` and
`MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR` are code defaults in current
implementation, not operator env variables. For normal event sizing, prefer
correct `target_capacity` in room config JSON. For practical VPS temporary
stress/emergency tuning, change only `BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE`
to the final desired number and restart `byod-backend`.

3) Per-IP reconnect/connect interval:
- `BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS` — per-IP Listener
  connect/reconnect throttle;
- baseline: `2 sec`;
- `0` disables this specific per-IP throttle;
- при NAT, public Wi-Fi или hotel networks несколько реальных пользователей
  могут выглядеть для backend как один public IP;
- этот лимит может складываться с `max_new_connections_per_sec`: сначала
  действует global new Listener connection rate, затем per-IP interval;
- loadgen bypass (`BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED` +
  `BYOD_LOADGEN_RECONNECT_BYPASS_KEY`) is only for controlled stress/load tests,
  not for real production/event traffic.

4) Active PLAY heartbeat control:
- после успешного backend WS connect backend ждёт `60 sec` первого ACTIVE PLAY trigger;
- Listener web page отправляет heartbeat каждые `10 sec` только при ACTIVE PLAY (`WAITING`/`PLAYING`);
- backend является единственным authority для stale-session решения:
  - если ACTIVE PLAY не был запущен за `60 sec` после connect, backend переводит listener session в reconnect-required и закрывает session;
  - если heartbeat отсутствует `60 sec` при active PLAY, backend помечает session как stale/reconnect-required;
  - backend удаляет stale listener из active session tracking/capacity accounting;
  - backend отправляет `reconnect_required` (если WS ещё writable), иначе просто закрывает/очищает session.

5) No-active-PLAY timeout recovery:
- Listener не решает stale по локальному 60-sec timer на основе отсутствия generic inbound WS traffic;
- reconnect Listener запускается только по allowed triggers:
  - `visibilitychange -> visible`,
  - `online`,
  - channel button click,
  - плюс bounded auto-retry policy while `UNAVAILABLE`.

Примечание:
- точные численные лимиты могут уточняться по результатам VPS stress test, но вышеуказанные значения считаются MVP baseline.

### 9.16. Backend endpoints

The current backend exposes only the endpoints below. The VPS nginx contract must keep `/admin/*` local-only and must not proxy admin paths publicly.

| Method | Path | Boundary | Purpose | Input/output shape |
|---|---|---|---|---|
| `GET` | `/health` | May be public through nginx. | Lightweight backend health check. | Returns `{"status":"ok"}`. |
| `POST` | `/admin/import_json` | Local-only; nginx must not expose `/admin/*`. | Imports and validates room config JSON, applies it to runtime state, persists state, and broadcasts updated state. | Multipart form upload field `file`; returns `{"ok": false, "errors": [...]}` or `{"ok": true, "applied": {"room_name": ..., "target_capacity": ..., "max_active_listeners": ..., "max_new_connections_per_sec": ..., "channels": ...}}`. |
| `GET` | `/admin/check_ws_compat` | Local-only; nginx must not expose `/admin/*`. | Builds Publisher and Listener state snapshots and verifies required schema keys for WebSocket compatibility. | Returns booleans such as `ok`, `publisher_state_ok`, `listener_state_ok`, plus schema versions. |
| `GET` | `/admin/metrics_snapshot` | Local-only; nginx must not expose `/admin/*`. | Provides machine-readable backend and LiveKit diagnostic counters for VPS metrics tooling. It must not include tokens, PINs, API secrets, or private environment dumps. | Returns `ts`, `ts_iso_msk`, room limits/status, backend session counts, reject counters, per-channel activity, and LiveKit participant diagnostics. |
| `POST` | `/admin/console_command` | Local-only; nginx must not expose `/admin/*`. | Executes an existing backend console command through the supported VPS control path. | JSON body `{"command":"help"}`; returns `{"ok": true, "command": "...", "result": "..."}`. |
| `WS` | `/ws/publisher` | Public WebSocket path through nginx. | Publisher WebSocket protocol for connect, heartbeat, ON AIR, and stop/off-air interactions. | Uses schema-versioned WebSocket envelopes from `docs/15_ws_schema_v1.md`; returns connect success/error and state updates. |
| `WS` | `/ws/listener` | Public WebSocket path through nginx. | Listener WebSocket protocol for connect, heartbeat, admission control, LiveKit token delivery, and reconnect-required signaling. | Uses schema-versioned WebSocket envelopes from `docs/15_ws_schema_v1.md`; returns connect success/error and listener state updates. |

Security notes:
- `/admin/*` endpoints enforce local-request checks in backend code and are local-only operational surfaces.
- nginx must expose only intended public paths (`/`, `/health`, `/ws/listener`, `/ws/publisher`) and must not expose `/admin/*`.
- Do not place secrets, PINs, API keys, or token examples in endpoint documentation or diagnostics output.

### 9.17. Backend console commands

Backend console commands are implemented in code and are available through the local-only admin endpoint. On VPS, operators must not type into systemd stdin. The supported VPS path is:

```text
POST http://127.0.0.1:8000/admin/console_command
```

The operator helper is:

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh help
```

Raw local endpoint shape:

```json
{"command":"help"}
```

Current commands:

| Command | Description |
|---|---|
| `help` | Print the supported command list. |
| `status` | Return room status, recording state, channel count, publisher/listener counts, target capacity, and derived listener admission limits. |
| `set_room_status <OPENED|BLOCKED|CLOSED>` | Change room status, persist state, and broadcast updated state. |
| `start_recording` | Mark recording active and persist recording/runtime state. |
| `stop_recording` | Mark recording inactive and persist recording/runtime state. |
| `set_channel_label <channel_id> <new_label>` | Update a channel label, persist state, log the change, and broadcast updated state. |
| `set_listen <channel_id> <true|false>` | Enable or disable Listener availability for a channel, persist state, log the change, and broadcast updated state. |
| `off_air <channel_id>` | Force-clear a channel owner, set its off-air timestamp, persist state, log the change, and broadcast updated state. |

Security notes:
- `/admin/console_command` is local-only.
- nginx must not expose `/admin/*`.
