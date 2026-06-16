# 22. Stress/load testing: Protocol/engine load и метрики VPS

## Назначение документа

Это постоянное руководство по нагрузочному тестированию BYOD на протяжении
жизненного цикла проекта, а не временный артефакт Stage XI. После крупных
изменений системы по нему повторно проверяется resource usage curve конкретного
VPS, стабильность длительной работы и поведение при деградации.

Implementation status: implemented for the first Stage XI tooling baseline.
Loader, Analyzer, `metrics_snapshot`, scripts и operator docs являются рабочими
implementation artifacts, которые могут уточняться по результатам реальных
прогонов.

## A. Scope

Stage XI проверяет только **Protocol/engine load**. Каждый виртуальный Listener
должен проходить реальный протокол backend и быть полноценным WebRTC/LiveKit
participant, но браузер и Web Listener UI не используются как генератор
нагрузки.

Browser/Web Listener UI load testing явно находится вне scope Stage XI.
Нагрузочное тестирование браузерного UI, DOM, rendering, browser audio output
и массового запуска вкладок относится к отдельной будущей задаче Web Listener
UI hardening.

Цель — выполнить capacity characterization для конкретного VPS и сравнивать
результаты между разными VPS configurations. Stage XI измеряет:

- как BYOD потребляет CPU;
- как BYOD потребляет RAM;
- как BYOD потребляет network RX/TX;
- как BYOD потребляет disk;
- как backend, LiveKit и nginx ведут себя при увеличении Listener count;
- observed stable range;
- observed degradation point;
- observed failure mode;
- resource usage curve для каждого профиля нагрузки;
- различия результатов между VPS configurations.

## B. Target environment

- Loader запускается оператором на Windows 10/11.
- Основной runtime — Python 3.11.
- Первая цель реализации — простой one-folder Python script.
- Позднее допустима упаковка PyInstaller в one-folder или one-file, только если
  она не замедляет MVP.
- Node.js допустим лишь как fallback, если Python-подход к LiveKit/WebRTC не
  заработает. Node.js не является предпочтительным вариантом.
- Серверная цель остаётся Ubuntu Server 22.04 LTS, один VPS, public IPv4.
- Рабочие инструменты оператора остаются PuTTY и WinSCP.

## C. Архитектура Loader

Путь:

```text
tools/load_test/
├── requirements.txt
├── byod_listener_loader.py
├── run_loader.bat          # optional
└── README.md
```

One-folder script здесь означает обычную папку со скриптом, зависимостями и,
опционально, вспомогательным `.bat`. Это не installable Python package.

Implementation status: implemented. Папка является one-folder script, а не
installable Python package.

## D. Модель подключения Loader

Каждый Listener worker обязан быть полноценным WebRTC participant и пройти
тот же путь, что нормальный Listener:

1. Выполнить HTTP preflight к VPS по IP, например запрос `/health`.
2. Подключиться к backend WebSocket через штатный Listener endpoint:
   `ws://<VPS_PUBLIC_IP>/ws/listener`.
3. Отправить стандартный WS schema v1 envelope `connecting` с ролью Listener.
4. Получить ответ backend `connecting` с `token`, `livekit_url` и
   `listener_id`.
5. Получить `i18n_library` и `listener_state`.
6. Подключиться к LiveKit с полученными `token` и `livekit_url`.
7. Выбрать один доступный для прослушивания канал.
8. Подписаться на audio track выбранного канала.
9. Продолжать получать media как LiveKit participant.
10. В первой реализации не декодировать и не воспроизводить звук через
    физический audio output.
11. Отправлять штатный Listener heartbeat:

    ```json
    {
      "client_role": "listener",
      "selected_channel": "<channel_id>",
      "playback_state": "PLAYING"
    }
    ```

12. Логировать ошибки, disconnect, reconnect и текущее состояние.

Ограничения:

- Loader не требует PIN.
- Loader получает только listener rights.
- Loader не использует Publisher endpoint.
- Loader не получает токены через отдельный admin endpoint и не обходит
  backend.
- Тест обязан проверять реальный Listener protocol и backend admission limits.

## E. Варианты backend endpoint

- Все Loader workers используют `/ws/listener`.
- `/admin/loader_token` для Stage XI не создаётся: такой endpoint обошёл бы
  реальный Listener protocol и лимиты.
- Первый предпочтительный источник LiveKit online counts — LiveKit API.
- Если LiveKit API нельзя быстро сделать доступным и надёжным, fallback для
  Analyzer — локальный endpoint:
  `GET http://127.0.0.1:8000/admin/metrics_snapshot`.
- `/admin/metrics_snapshot` должен быть local-only и не должен публиковаться
  через nginx.
- Implementation status: implemented; endpoint дополнительно проверяет loopback
  client и `X-Forwarded-For`.

## F. Runner identity

`runner_id` обязателен. Оператор вводит его вручную после остальных параметров
либо явно передаёт последним CLI-аргументом. Он отличает разные ПК, а также
несколько Loader instances на одном ПК.

Формат `worker_id`:

```text
<runner_id>-L<zero_padded_index>
```

Примеры:

- `home-pc1-L0001`
- `home-pc1-L0002`
- `gsm-laptop-L0001`
- `remote-pc3-L0412`

`connecting.payload` Loader может содержать диагностические metadata:

- `client_type: "load_runner"`
- `runner_id`
- `worker_id`
- `worker_index`
- `selected_channel_mode`

Эти поля диагностические и не должны ломать canonical protocol. Если backend
schema позднее станет строже, изменение schema docs должно быть отдельным,
осознанным решением.

## G. CLI

Обязательные параметры:

- URL/IP VPS;
- число listeners;
- `ramp-mode`: `linear` или `burst`;
- интервал запуска одного Listener каждые N секунд для `linear`;
- `channel-mode`: `random` или `fixed`;
- `channel-id` при `fixed`;
- hold duration;
- обязательный `runner_id`, запрашиваемый в конце или передаваемый явно.

Burst:

```bash
python tools/load_test/byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 50 ^
  --ramp-mode burst ^
  --channel-mode random ^
  --hold-sec 600 ^
  --runner-id home-pc1
```

Linear:

```bash
python tools/load_test/byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 500 ^
  --ramp-mode linear ^
  --listener-every-sec 0.25 ^
  --channel-mode random ^
  --hold-sec 900 ^
  --runner-id home-pc1
```

Fixed channel:

```bash
python tools/load_test/byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 100 ^
  --ramp-mode linear ^
  --listener-every-sec 0.5 ^
  --channel-mode fixed ^
  --channel-id channel_1 ^
  --hold-sec 900 ^
  --runner-id gsm-laptop
```

IP в примерах — адрес формата CLI-примера, а не credential или гарантия
доступности конкретного сервера.


## Валидность Protocol/engine run

Для валидного LiveKit subscription load недостаточно видеть только
`backend_connected`: это подтверждает лишь backend WebSocket. Минимальный
критичный сигнал для media/subscription нагрузки — confirmed
`livekit_track_subscribed`, который увеличивает `subscribed`. Если
`livekit_connected` растёт, а `subscribed` почти не растёт, запуск считать
`PARTIAL_RUN` или `INVALID_RUN` для capacity measurements до устранения причины.

## H. Выбор канала

- `channel-mode=random` случайно выбирает только канал с `listen=true`.
- `channel-mode=fixed` использует строго `--channel-id`.
- Если fixed channel отсутствует или имеет `listen=false`, Loader выполняет
  fail fast.
- Тихий fallback с fixed на random запрещён: он искажает валидность теста.
- Если backend не передал каналы за 60 секунд, Loader сообщает об ошибке.
- Если выбранный канал существует, но audio track сейчас не опубликован,
  Listener worker остаётся в room и ждёт без ограничения времени, как обычный
  Listener.
- Отсутствующий audio track сам по себе не означает отказ VPS.
- Ошибками считаются нарушения backend/LiveKit/connectivity/protocol.

## I. Audio/media behavior

Начальный режим реализации:

- подписаться на audio track выбранного канала;
- не создавать физическое audio playback;
- по возможности не выполнять decode/playback;
- проверить, действительно ли LiveKit передаёт media без чтения frames;
- если frames необходимо потреблять, позднее добавить опцию
  `--consume-audio-frames true`.

Это проверка валидности Protocol/engine load, а не функция UI. Базовые audio
инварианты проекта не меняются: 48000 Hz, stereo, frame size 960,
`track.name == channel_id`, selective subscribe и queue drop-oldest.

## J. Политика ручного ramp-up

- Оператор может запускать Loader несколько раз с одного или нескольких ПК.
- Manual ramp-up разрешён и ожидается.
- `runner_id` делает каждый запуск различимым в метриках.
- Для исключения локального интернет bottleneck можно использовать несколько
  ПК и разные подключения.
- Ориентир, сообщённый руководителем проекта: около 45 Mbit/s для одного
  Publisher плюс Listener loader. Допустимы дополнительные GSM и remote links.

Operational limits before profile runs:

- перед Baseline/High/Extreme operator может вручную настроить
  `target_capacity`, `max_new_connections_per_sec` и
  `listener_min_reconnect_interval_per_ip_seconds`;
- важные emergency/stress числа сгруппированы в верхнем operator block
  `src/backend/config.py`: изменить цифру, затем выполнить restart
  `byod-backend`;
- heartbeat/stale timings можно менять только осторожно, потому что они влияют
  на stale-session и reconnect_required behavior;
- `max_new_connections_per_sec` — global backend Listener admission rate;
- `listener_min_reconnect_interval_per_ip_seconds` — per-IP Listener
  connect/reconnect throttle;
- при запуске Loader с одного PC/NAT per-IP throttle может остановить Loader
  раньше, чем будет достигнута VPS capacity;
- это валидный сигнал для admission-control testing, но для capacity
  characterization limit может потребоваться аккуратно повысить или отключить.
- валидный Protocol/engine load run требует `livekit_track_subscribed` /
  `subscribed > 0`; одного backend Listener count недостаточно для
  media/subscription load measurement.

## K. Load profiles

### Baseline

| Поле | Значение |
|---|---|
| listeners | 50 |
| connection_rate_per_sec | текущий/default backend limit |
| hold | 10 минут |

Значение профиля:

- проверяет штатный backend listener limit и connection-rate controls;
- выполняется первым после рабочего deploy;
- не требует разблокировки конфигурации сверх нормальных deploy values.

### High

| Поле | Значение |
|---|---|
| listeners | 500 |
| connection_rate_per_sec | повышенный, но контролируемый |
| hold | 15 минут |

Значение профиля:

- проверяет практическую высокую нагрузку;
- connection rate вручную повышается в конфигурации до теста, но не становится
  unlimited;
- предпочтительный `ramp-mode` — `linear`;
- цель — стабильная ёмкость и контролируемая деградация, а не мгновенный crash.

### Extreme

| Поле | Значение |
|---|---|
| listeners | 2000 |
| connection_rate_per_sec | повышенный для stress |
| hold | 20 минут |

Значение профиля:

- ищет верхнюю границу и failure modes;
- config limits вручную меняются до теста;
- ограничения интернета и Loader client могут потребовать несколько ПК/links;
- деградация или crash допустимы как результат, если они измерены.

Дополнительные простые опции профиля:

- `ramp-mode: burst | linear`
- `channel-mode: random | fixed`
- `heartbeat-sec: 10`
- `connect-timeout-sec: 30`
- `channels-timeout-sec: 60`
- `reconnect: true | false`

### HOLD

`hold` / HOLD — это observation period после завершения ramp-up. Во время HOLD
каждый Listener worker сохраняет активными:

- backend WebSocket;
- LiveKit connection;
- selected channel subscription;
- Listener heartbeat.

HOLD используется для сбора steady-state VPS/resource metrics: CPU, RAM,
network RX/TX, disk, backend/LiveKit/nginx status и counts. HOLD не является
pass/fail target. Если запуск деградировал или завершился во время HOLD, он всё
равно может дать полезные данные об observed degradation point или observed
failure mode, если метрики собраны достаточно полно.

Профили являются documentation/manual targets. Автоматическое редактирование
конфигурации не реализуется. Фактические backend config values оператор вручную
меняет после deploy перед соответствующим профилем.

## L. VPS Analyzer

Команда управления:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh start|stop|status
```

Analyzer должен:

- работать через systemd, а не через `nohup` или pid-only shell background;
- использовать service name `byod-metrics-analyzer.service`;
- работать в фоне до явной остановки;
- по умолчанию снимать sample каждые 120 секунд;
- переживать закрытие окна PuTTY благодаря systemd;
- при перегрузке или reboot VPS естественно остановиться, сохранив уже
  записанные на диск логи.

Implementation status: implemented. Script создаёт/обновляет systemd service
unit при `start`.

## M. Путь вывода Analyzer

Каталог:

```text
/opt/byod/metrics/
```

Файлы одного запуска:

```text
/opt/byod/metrics/byod_metrics_<timestamp>.csv
/opt/byod/metrics/byod_metrics_<timestamp>.jsonl
/opt/byod/metrics/byod_metrics_<timestamp>.log
```

Operator commands:

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh start
sudo bash deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh status
sudo bash deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh stop
```

Local metrics snapshot check на VPS:

```bash
curl -s http://127.0.0.1:8000/admin/metrics_snapshot
```

Manual resource viewer:

```bash
btop
```

## N. Метрики Analyzer

Минимальный набор:

- `timestamp_local`
- `timestamp_utc`
- `cpu_percent`
- `ram_used_gb`
- `ram_total_gb`
- `disk_used_gb`
- `disk_total_gb`
- `net_iface`
- `rx_mbps`
- `tx_mbps`
- `livekit_publishers_count`
- `livekit_listeners_count`
- `livekit_rooms_count`
- `backend_publishers_count`
- `backend_listeners_count`
- `backend_active_play_count`
- `byod_backend_status`
- `byod_livekit_status`
- `nginx_status`

CSV предназначен для таблиц, JSONL — для machine parsing, human-readable
`.log` — для быстрого ручного просмотра. Временные отметки должны быть понятны
оператору: одновременно записываются local и UTC timestamps.

## O. Стратегия источников метрик

1. Сначала использовать LiveKit API для количества rooms, participants,
   Publisher и Listener.
2. Если LiveKit API нельзя быстро и надёжно использовать, получать fallback из
   `GET http://127.0.0.1:8000/admin/metrics_snapshot`.
3. `/admin/metrics_snapshot` остаётся local-only и не публикуется через nginx.
4. Endpoint имеет implementation status: implemented.
5. Machine-readable JSON должен содержать как минимум:

   - `ts`;
   - `room_status`;
   - `target_capacity`;
   - `max_active_listeners`;
   - `max_new_connections_per_sec`;
   - `backend_publishers_count`;
   - `backend_listeners_count`;
   - `backend_active_play_count`;
   - `backend_listeners_by_runner`;
   - channel summary с `channel_id`, `listen`, `owner` и, если доступно,
     `active_listeners`.

## P. Deploy requirement

`btop` должен автоматически устанавливаться при подготовке Stage X/Stage XI
VPS. `00_prepare_host.sh` добавляет `btop` в host packages.

## Q. Run validity categories

Stage XI не является проверкой фиксированного capacity ceiling. Основная цель —
измерение и сравнение resource usage curve, observed stable range, observed
degradation point и observed failure mode. Для оценки качества данных
используются run-validity categories:

- **VALID RUN** — metrics complete enough for analysis. Данных достаточно,
  чтобы построить resource usage curve и описать поведение backend, LiveKit и
  nginx при заданном Listener count.
- **PARTIAL RUN** — тест деградировал или завершился раньше ожидаемого HOLD, но
  собранные данные всё ещё полезны для анализа observed degradation point или
  observed failure mode.
- **INVALID RUN** — данным нельзя доверять из-за ошибки Loader, Analyzer,
  config, setup или другой проблемы методики; такой запуск не используется для
  сравнения VPS configurations.

Числовые thresholds могут появиться после накопления измерений, но они не
заменяют raw metrics и не являются основной целью Stage XI.
