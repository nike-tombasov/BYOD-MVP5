# Stage XI Listener Loader для Protocol/engine load

## 1. Что делает Loader

Loader запускается на Windows 10/11 и создаёт заданное число synthetic Listener workers. Каждый Listener worker:

- выполняет HTTP preflight `/health`;
- подключается к backend WebSocket `/ws/listener`;
- отправляет обычный Listener `connecting` envelope schema v1;
- получает `token`, `livekit_url`, `listener_id`, `i18n_library` и `listener_state`;
- подключается к LiveKit как реальный WebRTC participant;
- выбирает listenable channel;
- подписывается на audio track выбранного канала;
- отправляет Listener heartbeat с `playback_state: "PLAYING"`;
- остаётся подключённым во время HOLD.

## 2. Что Loader не делает

- Не открывает Web Listener UI и browser.
- Не требует PIN.
- Не использует Publisher endpoint.
- Не получает token через отдельный admin endpoint.
- Не воспроизводит audio на физическое устройство.
- Не меняет audio constants, `track.name == channel_id` или selective subscribe rule.

Если LiveKit не отправляет media без потребления frames, это будет отдельная проверка валидности теста. Будущая опция зарезервирована как `--consume-audio-frames true`, но в первой реализации она не требуется.

## 3. Требования Windows 10/11

- Windows 10 или Windows 11.
- Доступ к VPS по сети.
- Python 3.11 установлен и доступен через launcher `py -3.11`.
- Консоль: Windows Terminal, PowerShell или `cmd.exe`.

## 4. Как открыть console

1. Откройте папку `tools\load_test` через File Explorer.
2. В адресной строке введите `cmd` и нажмите Enter.
3. Или откройте Windows Terminal и выполните:

```bat
cd path\to\BYOD-MVP5\tools\load_test
```

## 5. Создание venv и установка зависимостей

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Можно также использовать helper:

```bat
run_loader.bat --help
```

`run_loader.bat` создаёт `.venv`, устанавливает requirements и запускает Loader с переданными параметрами.

## 6. Проверка 1 Listener перед нагрузкой

Перед ramp tests обязательно проверьте один Listener в `DEBUG` mode:

```bat
py -3.11 tools\load_test\byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 1 ^
  --ramp-mode burst ^
  --channel-mode fixed ^
  --channel-id channel_1 ^
  --hold-sec 120 ^
  --runner-id debug-pc1 ^
  --log-level DEBUG
```

Ожидаемая последовательность в logs:

- `backend_ws_connected`
- `backend_connecting_ok`
- `listener_state_received`
- `livekit_connected`
- `livekit_publication_seen`
- `livekit_subscription_requested`
- `livekit_track_subscribed`

`backend_connected=1` сам по себе недостаточен. Для валидной media/subscription
нагрузки `subscribed` должен стать `1`, а событие `livekit_track_subscribed`
должно появиться в log. Если есть только `livekit_selected_track_waiting`,
значит Loader подключён к backend/LiveKit, но ещё не видит подходящий audio
publication для выбранного `channel_id`; ramp tests запускать рано.

## 7. Baseline example

```bat
python byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 50 ^
  --ramp-mode burst ^
  --channel-mode random ^
  --hold-sec 600 ^
  --runner-id home-pc1
```

## 8. High example

```bat
python byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 500 ^
  --ramp-mode linear ^
  --listener-every-sec 0.25 ^
  --channel-mode random ^
  --hold-sec 900 ^
  --runner-id home-pc1
```

## 9. Extreme example

Extreme может упереться в интернет оператора или CPU/RAM клиентского ПК. Разрешён manual ramp-up с нескольких PC/network links.

```bat
python byod_listener_loader.py ^
  --server http://80.78.244.210 ^
  --listeners 2000 ^
  --ramp-mode linear ^
  --listener-every-sec 0.1 ^
  --channel-mode random ^
  --hold-sec 1200 ^
  --runner-id remote-pc3
```

## 10. Как выбрать runner_id

`runner_id` обязателен и вручную задаётся оператором. Он должен отличать PC или конкретный Loader run.

Примеры:

- `home-pc1`
- `home-pc1-run2`
- `gsm-laptop`
- `remote-pc3`

Worker IDs формируются автоматически:

- `home-pc1-L0001`
- `home-pc1-L0002`

## 11. Channel mode

Random:

```bat
--channel-mode random
```

Loader выбирает случайно только channels, где `listen=true`.

Fixed:

```bat
--channel-mode fixed --channel-id channel_1
```

Если fixed channel отсутствует или `listen=false`, Loader делает fail fast. Он не переключается молча на random, чтобы не испортить валидность измерения.

## 12. Где лежат logs

Loader пишет в локальную папку:

```text
tools\load_test\logs\
```

Файлы одного запуска:

- human-readable `.log`;
- worker events `.jsonl`;
- summary `.csv`.

Tokens, PIN и secrets не логируются. В событиях указывается `worker_id`.

В live counters:

- `backend_connected` означает только backend WebSocket session;
- `livekit_connected` означает WebRTC room connection;
- `subscription_requested` означает, что Loader запросил подписку на selected channel;
- `subscribed` означает подтверждённое событие `livekit_track_subscribed`;
- `waiting_for_track` означает ожидание подходящей LiveKit audio publication.

Для валидной Protocol/engine media load проверки нужен `subscribed > 0`.

## 13. Что означает HOLD

HOLD начинается после завершения ramp-up. Во время HOLD Listener workers сохраняют:

- backend WebSocket;
- LiveKit connection;
- selected channel subscription;
- heartbeat.

HOLD нужен для steady-state метрик VPS Analyzer. HOLD не является pass/fail target. Если система деградирует во время HOLD, собранные метрики всё равно могут быть полезны для observed degradation point и observed failure mode.

## 14. Как остановить

Нажмите `Ctrl+C` в console. Loader попытается закрыть backend WebSocket и LiveKit connection cleanly.

## 15. Что означают ошибки

- `no channels received within channels timeout` — backend не прислал channels за `--channels-timeout-sec`.
- `fixed channel not found` — `--channel-id` отсутствует в `listener_state`.
- `fixed channel is not listenable` — channel есть, но `listen=false`.
- `backend websocket failed` / connection exception — ошибка подключения к `/ws/listener` или backend reject.
- `LiveKit connect failed` — token/livekit_url получены, но WebRTC connection не установлен.
- `livekit_selected_track_waiting` — selected channel есть, но matching LiveKit
  audio publication ещё не видна; worker остаётся подключённым, heartbeat
  продолжается, это не автоматический VPS failure.
- отсутствие `livekit_track_subscribed` — Loader ещё не подтвердил реальную
  LiveKit subscription; такой запуск не готов для capacity measurements.
- `reconnecting` — worker повторяет попытку, если включён `--reconnect true` или `--reconnect`.

## 16. PyInstaller

PyInstaller packaging опционален и не требуется для первых запусков. Сначала запускайте Loader из `.venv`. Упаковку можно рассмотреть позже, если она не замедляет MVP и не мешает диагностике.
