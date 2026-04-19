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
6) room status - room_status (close - по умолчанию во время запуска сервера)
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

Admin изменяет room status вручную. Room status не приостанавливает streaming, publishing, sending frames и никак не влияет на работу Publisher.

* OPENED - start channel mult-itrack recording, listener может получать звук, subscribe on tracks
* BLOCKED - приостановка получения звуков для listener, forced unsubscribe до возвращения room status OPENED, status custom text
* CLOSED - приостановка получения звуков для listener, forced unsubscribe до возвращения room status OPENED, стоп записи channel multi-track recording, web page status custom text

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

Защититься от гонок (atomic updates). Лимитировать давность поступившего запроса в 30 секунд при расхождение request on air timestamp от current time на случай зависания Publisher или обрывов интернет соединения (ввиду потенциальной неактуальности, чтобы не оборвать актуальный Publisher).
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

### 9.9. Channel multi-track recording

После перевода room status to OPENED recording стартуется автоматически. Старт должен быть одновременным по всем channel_id

Требования к записи:
* MP3 
* 192 kbps
* stereo
* 48000 hz
* каждый channel_id - отдельный файл mp3
* имя файла - timestamp-channel_id-channel_label

При изменении channel_label во время recording изменение имени файлов аудиозаписей происходит только при ручном перезапуске записи или при череде смены room status OPENED -> CLOSED -> OPENED.

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
7) ручной старт/стоп channel multi-track recording (автоматически запускается при переходе комнаты в статус OPENED и останавливается при переходе в CLOSED)
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

Для MVP Stage VII-IX вводятся базовые защитные лимиты:

1) Hard limit active listeners:
- `max_active_listeners = target_capacity * 1.05`
- при превышении новых listeners не подключать (возврат отказа подключения).

2) Rate-limit new connections:
- максимум `target_capacity / 15` новых Listener подключений в секунду.

3) Minimal reconnect interval:
- для одного listener identity/IP новый reconnect допускается только при интервале `> 2 sec`.

4) Active PLAY heartbeat control:
- Listener web page starts heartbeat loop right after successful backend WS connect and sends heartbeat every `10 sec`.
- Heartbeat payload includes playback state; backend stale authority still applies only for active PLAY sessions.
- backend является единственным authority для stale-session решения:
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
