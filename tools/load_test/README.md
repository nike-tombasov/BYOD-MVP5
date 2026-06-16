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

Перед ramp tests обязательно проверьте один Listener с Publisher, уже streaming `channel_1`:

```bat
py -3.11 tools\load_test\byod_listener_loader.py ^
  --server http://127.0.0.1:8000 ^
  --listeners 1 ^
  --ramp-mode burst ^
  --channel-mode fixed ^
  --channel-id channel_1 ^
  --hold-sec 120 ^
  --runner-id test1 ^
  --log-level INFO
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
- `livekit_selected_track_waiting` — selected channel publication ещё не видна
  или manual subscription уже запрошена и Loader ждёт `track_subscribed`; worker
  остаётся подключённым, heartbeat продолжается, это не автоматический VPS
  failure.
- publication видна, но `track_present=False` — это нормально до manual
  subscription при `RoomOptions(auto_subscribe=False)`. Loader должен вызвать
  `publication.set_subscribed(True)`, после чего LiveKit SDK пришлёт
  `track_subscribed` и заполнит `publication.track`. `track_present=False` сам
  по себе не доказывает, что Publisher не streaming.
- `livekit_track_subscription_failed` — LiveKit отклонил manual subscription;
  смотрите `participant_identity`, `track_sid`, `error` и `selected_channel`.
- отсутствие `livekit_track_subscribed` — Loader ещё не подтвердил реальную
  LiveKit subscription; такой запуск не готов для capacity measurements.
  Валидный run требует `livekit_track_subscribed`, а не только
  `livekit_publication_seen`.
- `reconnecting` — worker повторяет попытку, если включён `--reconnect true` или `--reconnect`.

## 16. PyInstaller

PyInstaller packaging опционален и не требуется для первых запусков. Сначала запускайте Loader из `.venv`. Упаковку можно рассмотреть позже, если она не замедляет MVP и не мешает диагностике.

## 17. Ctrl+C shutdown и нормальное закрытие

`Ctrl+C` является штатным способом остановки. Loader ставит общий stop flag,
даёт worker'ам короткое время закрыть heartbeat/subscription monitor, затем
закрывает LiveKit room и backend WebSocket с normal close. Backend close code
`1000` считается нормальным shutdown, а не ошибкой; в JSONL появляется
`backend_ws_closed_normal`, если backend WS закрылся во время остановки.

Сообщение `Event loop is closed` после `Ctrl+C` означает shutdown bug и не
должно повторяться или заливать console/log.

## 18. loader_run_id и несколько окон Loader

`runner_id` остаётся обязательным и читаемым идентификатором ПК/оператора.
`worker_id` остаётся в формате:

```text
<runner_id>-L0001
```

Каждый запуск дополнительно имеет `loader_run_id`. Его можно передать явно:

```bat
--loader-run-id home-pc1-window-a
```

Если параметр не задан, Loader создаёт значение автоматически:

```text
<runner_id>-<YYYYMMDD-HHMMSS>-pid<PID>
```

`loader_run_id` попадает в каждое JSONL event, имена `.log`/`.jsonl`/`.csv`, и
backend diagnostic metadata вместе с `runner_id`, `worker_id` и
`worker_index`. Поэтому несколько Loader windows из одной папки и с одного ПК
разрешены: используйте одинаковый `runner_id` для ПК и разные автоматические
или ручные `loader_run_id` для run separation.

## 19. Валидность run и subscribed

Для LiveKit subscription load ключевой минимум — confirmed
`livekit_track_subscribed`. `backend_connected` означает только, что backend
WebSocket принят, и сам по себе не является валидным media/subscription load
test.

В финальном summary смотрите:

- `backend_connected` — backend WebSocket session;
- `livekit_connected` — LiveKit room connection;
- `subscription_requested` — Loader запросил selected channel subscription;
- `subscribed` — LiveKit подтвердил `livekit_track_subscribed`;
- `run_validity` — `VALID_RUN`, `PARTIAL_RUN` или `INVALID_RUN`.

Если много `livekit_connected`, но мало `subscribed`, LiveKit subscription side
ещё не валиден для capacity measurements. Для debug можно задать
`--subscription-timeout-sec N`; default `0` ждёт indefinitely и не fail'ит
worker только из-за pending subscription.

## 20. JSONL рост и debug-publications

По умолчанию JSONL уважает `--log-level` и не пишет безлимитный поток DEBUG
событий. Publication/participant шум ограничен: Loader пишет небольшой initial
inventory, selected channel match/state change, subscription requested и
subscription confirmed. Полный поток публикаций включается только флагом:

```bat
--debug-publications
```

Высокий рост JSONL обычно означает, что включён `--debug-publications` или
сломался rate limiting для publication/participant events.

## 21. Запуск Loader со второго ПК в локальной сети

Сценарий: backend и LiveKit запущены на ПК-1, а Loader запускается на втором Windows ПК в той же локальной сети.

1. На ПК-1 найдите LAN IP:

```bat
ipconfig
```

Пример далее: `ПК-1 LAN IP = 192.168.1.50`.

2. Backend на ПК-1 должен слушать все сетевые интерфейсы:

```env
BYOD_BACKEND_HOST=0.0.0.0
BYOD_BACKEND_PORT=8000
```

3. Backend должен отдавать Loader LAN-доступный LiveKit URL:

```env
BYOD_LIVEKIT_URL=ws://192.168.1.50:7880
```

`ws://127.0.0.1:7880` здесь неправильно: для Loader на другом ПК `127.0.0.1` означает сам второй ПК, а не ПК-1 с LiveKit.

4. CORS для локального web origin может быть:

```env
BYOD_CORS_ALLOWED_ORIGIN=http://192.168.1.50:8000
```

5. На ПК-1 нужны Windows Firewall inbound rules:

- TCP 8000
- TCP 7880
- TCP 7881
- UDP 50000-50100

PowerShell от администратора на ПК-1:

```powershell
New-NetFirewallRule -DisplayName "BYOD Backend 8000 TCP" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
New-NetFirewallRule -DisplayName "BYOD LiveKit 7880 TCP" -Direction Inbound -Protocol TCP -LocalPort 7880 -Action Allow
New-NetFirewallRule -DisplayName "BYOD LiveKit 7881 TCP" -Direction Inbound -Protocol TCP -LocalPort 7881 -Action Allow
New-NetFirewallRule -DisplayName "BYOD LiveKit UDP 50000-50100" -Direction Inbound -Protocol UDP -LocalPort 50000-50100 -Action Allow
```

6. На втором ПК проверьте TCP доступность:

```powershell
Test-NetConnection 192.168.1.50 -Port 8000
Test-NetConnection 192.168.1.50 -Port 7880
Test-NetConnection 192.168.1.50 -Port 7881
```

7. Команда Loader со второго ПК:

```bat
py -3.11 tools\load_test\byod_listener_loader.py ^
  --server http://192.168.1.50:8000 ^
  --listeners 1 ^
  --ramp-mode burst ^
  --channel-mode fixed ^
  --channel-id channel_1 ^
  --hold-sec 120 ^
  --runner-id pc2-test ^
  --log-level INFO
```

Ожидаемый success:

- `backend_connecting_ok`
- `livekit_url=ws://192.168.1.50:7880`
- `livekit_connected`
- `livekit_subscription_requested`
- `livekit_track_subscribed`
- `FINAL subscribed=1 VALID_RUN`

## 22. Безопасный multi-PC ramp

Начинайте multi-PC тесты с плавного ramp:

```bat
--listener-every-sec 1
```

Пример безопасной последовательности:

- PC1: 120 listeners, every 1 sec;
- PC2: 50 listeners, every 1 sec;
- затем PC2: 120 listeners, every 1 sec.

Не начинайте с `--listener-every-sec 0.1` сразу на нескольких ПК. Это означает примерно 10 workers/sec, а не 0.1 worker/sec. Быстрый ramp может временно оставить часть workers в `livekit_subscription_pending`; это не автоматическое доказательство backend failure, если позже они переходят в `livekit_track_subscribed`.

## 23. LiveKit visibility и troubleshooting

Local-only backend metrics:

```bash
curl -s http://127.0.0.1:8000/admin/metrics_snapshot
```

Endpoint остаётся доступным только локально на backend host и не публикуется через nginx. LiveKit API gives room/participant visibility: кто находится в room и какие tracks участники публикуют. Он не доказывает каждую subscription на каждый track. Confirmed subscription load пока проверяется в первую очередь по Loader counters/events `livekit_track_subscribed` / `subscribed`, пока не добавлена более точная server-side subscription metric.

Decision table:

| Вероятная зона | Признаки |
|---|---|
| Backend/admission likely issue | `backend_connected` much lower than target; backend logs show connection rate/reconnect/room-full rejects. |
| LiveKit/server likely issue | `backend_connected` normal; `livekit_connected` much lower; LiveKit logs show participant disconnect/failure; LiveKit API participants do not match backend sessions. |
| Loader/subscription likely issue | `backend_connected` normal; `livekit_connected` normal; `subscription_requested` normal; `subscribed` lags but catches up with slower ramp; browser Listener hears audio at the same time. |

## Portable Windows package без PyInstaller

Для операторов, которым нужен запуск без установки Python, venv и `pip` на целевом Windows 10/11 x64 ПК, поддерживается one-folder portable package:

```text
dist\BYOD-Loader-Portable-Win64\
```

Package использует embedded/portable CPython runtime в подпапке `python\`; PyInstaller не используется и single `.exe` не создаётся. Backend protocol, Web Listener UI, Publisher, audio constants и LiveKit track naming не меняются.

Сборка на developer/build Windows PC с Python 3.11 и internet:

```powershell
powershell -ExecutionPolicy Bypass -File tools\load_test\portable\build_portable_loader.ps1
```

Если embedded Python zip уже скачан локально:

```powershell
powershell -ExecutionPolicy Bypass -File tools\load_test\portable\build_portable_loader.ps1 -PythonEmbedZip C:\path\python-3.11.x-embed-amd64.zip
```

Builder создаёт:

```text
dist\BYOD-Loader-Portable-Win64\
dist\BYOD-Loader-Portable-Win64.zip
```

Target-user запуск после копирования/распаковки папки:

```bat
run_loader.bat
```

Advanced запуск с полными аргументами:

```bat
run_loader_args.bat --server http://192.168.1.50:8000 --listeners 50 --ramp-mode linear --listener-every-sec 1 --channel-mode fixed --channel-id channel_1 --hold-sec 600 --runner-id pc2
```

Builder валидирует portable runtime командами `python.exe app\byod_listener_loader.py --help` и import check для `websockets`, `livekit.rtc`, `livekit.api`; при ошибке сборка останавливается с non-zero exit code.
