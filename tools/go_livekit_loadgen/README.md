# BYOD Go LiveKit loadgen — русское руководство

## 1. Что это

`tools/go_livekit_loadgen/` — текущий Go loadgen для stress/load testing BYOD. Он создает эмулированных Listener-воркеров, проходит обычный backend listener admission path и, в режимах LiveKit, использует данные, которые backend выдает слушателю.

Инструмент Windows-first: основной переносимый пакет собирается под Windows/Win64, а вспомогательные `.bat` файлы рассчитаны на операторские Windows-машины. При этом сам Go binary можно запускать там, где доступна подходящая сборка Go-программы.

Это не browser UI testing. Loadgen проверяет protocol/engine path, а не массовую работу реальных вкладок Web Listener, autoplay, audio device output, CSS/layout или UX.

## 2. Рубежи/Gates

### Gate A — `backend-ws-only`

Проверяет backend WebSocket путь Listener: подключение к `/ws/listener`, обычный listener protocol, heartbeat и удержание соединений во время HOLD. В профиле `vps-nginx` backend WebSocket идет через nginx.

Не проверяет LiveKit, ICE, audio subscription, RTP, браузерное воспроизведение или media egress.

### Gate B — `livekit-connect-only`

Проверяет backend admission плюс подключение worker как LiveKit participant. Режим нужен, чтобы отделить проблемы backend WebSocket от проблем LiveKit signaling/participant connection.

Не подписывается на audio tracks и не проверяет RTP/media flow.

### Gate C — `livekit-subscribe-discard-rtp`

Проверяет backend admission, LiveKit connect, audio track subscription и получение RTP packets с немедленным discard payload. Opus не декодируется, физический audio output не используется.

Это media-engine нагрузка, но не доказательство работы сотен реальных браузеров.

## 3. Быстрый старт

Запускайте команды из каталога `tools/go_livekit_loadgen/`. Во всех примерах замените `http://<VPS_PUBLIC_IP>` и `byod_loadgen_key_01` на значения текущего стенда.

### A50 now

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode backend-ws-only `
  -server http://<VPS_PUBLIC_IP> `
  -listeners 50 `
  -start-at now `
  -start-mode burst `
  -burst-size 50 `
  -burst-interval-ms 0 `
  -hold-sec 45 `
  -target-wait-sec 20 `
  -backend-connect-timeout-sec 10 `
  -runner-id win1-a50 `
  -loadgen-key byod_loadgen_key_01 `
  -out-dir out/win1-a50
```

### B50 now

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode livekit-connect-only `
  -server http://<VPS_PUBLIC_IP> `
  -listeners 50 `
  -start-at now `
  -start-mode burst `
  -burst-size 50 `
  -burst-interval-ms 0 `
  -hold-sec 45 `
  -target-wait-sec 20 `
  -backend-connect-timeout-sec 10 `
  -runner-id win1-b50 `
  -loadgen-key byod_loadgen_key_01 `
  -out-dir out/win1-b50
```

### C30/C50 selected now

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode livekit-subscribe-discard-rtp `
  -subscribe-mode selected `
  -server http://<VPS_PUBLIC_IP> `
  -listeners 30 `
  -start-at now `
  -start-mode burst `
  -burst-size 30 `
  -burst-interval-ms 0 `
  -hold-sec 45 `
  -target-wait-sec 20 `
  -backend-connect-timeout-sec 10 `
  -runner-id win1-c30 `
  -loadgen-key byod_loadgen_key_01 `
  -out-dir out/win1-c30
```

Для C50 используйте `-listeners 50`, `-burst-size 50`, другой `-runner-id` и другой `-out-dir`.

### Синхронный B100 с `-start-at <RFC3339 timestamp>`

`-start-at now` запускает сразу. RFC3339 timestamp заставляет loadgen ждать указанного будущего времени, а затем запускать worker по форме, заданной `-start-mode`.

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode livekit-connect-only `
  -server http://<VPS_PUBLIC_IP> `
  -listeners 100 `
  -start-at 2026-06-27T22:30:00+03:00 `
  -start-mode burst `
  -burst-size 50 `
  -burst-interval-ms 1000 `
  -hold-sec 60 `
  -target-wait-sec 30 `
  -backend-connect-timeout-sec 10 `
  -runner-id win1-b100-sync `
  -loadgen-key byod_loadgen_key_01 `
  -out-dir out/win1-b100-sync
```

## 4. Все флаги

### Core

- `-profile` — профиль окружения. Допустимые значения: `local-direct`, `vps-nginx`. Default: пусто, нужно задать явно. Меняйте при переключении между прямым локальным backend и VPS/nginx. Частая ошибка: забыть профиль.
- `-mode` — gate/mode. Допустимые значения: `backend-ws-only`, `livekit-connect-only`, `livekit-subscribe-discard-rtp`. Default: пусто, нужно задать явно. Меняйте только по сценарию Gate A/B/C.
- `-server` — base URL сервера, например `http://127.0.0.1:8000` или `http://<VPS_PUBLIC_IP>`. Default: пусто, нужно задать явно. Из него строится Listener WebSocket path `/ws/listener`; при `https` используется `wss`.
- `-listeners` — целевое число worker/listener. Default: `0`, нужно задать `>= 1`. Увеличивайте постепенно.
- `-required-listeners` — сколько listener нужно для старта HOLD и оценки цели. Default: `0`, после validation становится равно `-listeners`. Меняйте только для осознанных частичных проверок.
- `-exact-target` — требует полный target для official proof. Default: `true`. Если хотите `-required-listeners` меньше `-listeners`, нужно явно поставить `-exact-target=false`.

### Start/ramp

- `-start-at` — когда начинать запуск worker: `now` или будущий RFC3339 timestamp. Default: `now`. `now` означает немедленно; RFC3339 означает ждать до этого времени. Частая ошибка: указать время в прошлом.
- `-start-mode` — форма запуска worker после наступления `-start-at`. Допустимые значения: `ramp`, `burst`. Default: `ramp`. Этот флаг не синхронизирует сам по себе; синхронизацию задает `-start-at`.
- `-ramp-per-sec` — скорость запуска worker в режиме `-start-mode ramp`. Default: `0`, но для `ramp` нужно задать `>= 1`. В режиме `burst` при значении `< 1` validation приводит его к `1`, но фактическую форму запуска задают burst-флаги.
- `-burst-size` — сколько worker запускать за один burst. Default: `0`; при `-start-mode burst` нужно задать `>= 1`.
- `-burst-interval-ms` — пауза между burst в миллисекундах. Default: `1000`. Значение `0` означает без паузы между burst.

### Timing

- `-hold-sec` — длительность HOLD после достижения gate-specific target. Default: `0`, нужно задать `>= 1`.
- `-target-wait-sec` — сколько секунд ждать достижения target после завершения запуска всех worker. Default: `15`. Увеличивайте для медленных стендов или больших запусков.
- `-backend-connect-timeout-sec` — timeout backend connect / first message для worker. Default: `10`. Увеличивайте при медленной сети; слишком маленькое значение создает ложные backend timeout.

### Gate C/media

- `-subscribe-mode` — режим подписки для Gate C. Допустимые значения: `selected`, `all`. Default: `selected`. Для Gate A/B допустим только default `selected`; явное `all` вне Gate C rejected validation. Обычно используйте `selected`, чтобы проверять выбранный канал worker.

### Output/identity

- `-runner-id` — обязательный ID машины/запуска. Default: пусто, нужно задать явно. Используйте уникальные значения, например `win1-b50`, чтобы разделять логи и worker identity.
- `-loadgen-key` — обязательный loadgen key, который worker отправляет в backend metadata/diagnostics. Default: пусто, нужно задать явно. Это не самостоятельный capacity bypass и не замена backend admission.
- `-out-dir` — директория для output. Default: `./out`. Внутри создаются `events_*.jsonl` и `summary_*.json`.

### Diagnostics

Отдельных CLI-флагов diagnostics сейчас нет. Диагностические данные попадают в live terminal output, `events_*.jsonl` и `summary_*.json`; VPS-side diagnostics собираются отдельными серверными helper scripts.

## 5. Как читать результат

- `VALID_RUN` — достигнут gate-specific required target, HOLD завершен, нет критичных shortfall/terminal проблем, summary достаточно надежен на верхнем уровне.
- `PARTIAL_RUN` — собраны полезные данные, но target/HOLD/terminal условия не полностью выполнены.
- `INVALID_RUN` — setup/generator/config/metrics сломались так, что capacity interpretation ненадежна.
- `backend_shortfall` — сколько worker не дошли до backend connected относительно `-listeners`.
- `livekit_shortfall` — сколько worker не дошли до LiveKit connected относительно `-listeners`.
- `audio_shortfall` — сколько worker в Gate C не получили audio track относительно `-listeners`.
- `rtp_shortfall` — сколько worker в Gate C не получили RTP относительно `-listeners`.
- `workers_without_terminal_event` — сколько started worker не дали финальное terminal событие. Для доверия к итогам желательно `0`.
- `workers_failed_terminal` — сколько worker завершились terminal status, отличным от `completed` или `normal_shutdown`.
- `partial_reason` — причина частичного результата, например timeout ожидания цели, невозможность цели после terminal failure или context/manual cancellation.
- `first_target_shortfall_stage` — первый stage, где target не достигнут: `backend`, `livekit`, `audio` или `rtp`.
- RTP counters: `rtp_packets`, `rtp_bytes`, `rtp_read_errors`, `workers_with_rtp`, `rtp_target_reached`. Для Gate C важно, чтобы пакеты и байты росли, а read errors не объясняли результат.
- Transport counters: `transport_udp`, `transport_tcp`, `transport_unknown`, `udp_tcp_ratio`. Они полезны для live view, но окончательный transport forensic может требовать server-side log correlation.

## 6. Что собирать после запуска

Всегда сохраняйте:

- `summary_*.json`;
- `events_*.jsonl`, если файл доступен и не удален;
- точную команду запуска или соответствующий `.bat`;
- `runner-id`;
- время запуска и профиль стенда.

Для `PARTIAL_RUN`, `INVALID_RUN`, подозрительных результатов или runs около capacity boundary дополнительно собирайте VPS diagnostics: metrics snapshots, nginx/backend/livekit tails, `/opt/byod/metrics`, `/opt/byod/diagnostics` и operator screenshot, если он есть.

## 7. Portable package

Portable Win64 package собирается скриптом:

```powershell
cd tools/go_livekit_loadgen
.\scripts\build_portable_windows.ps1
```

Скрипт выполняет `go mod tidy`, `go test ./...`, собирает `byod-loadgen.exe`, создает `.bat` wrappers и архив `dist/BYOD-Loadgen-Portable-Win64.zip`.

На helper machines Go не нужен: оператор распаковывает zip, открывает нужный `.bat` и редактирует верхние переменные:

- `SERVER` — адрес стенда;
- `RUNNER_ID` — уникальный ID машины/запуска;
- `LOADGEN_KEY` — ключ текущего stress event;
- `START_AT` — `now` или общий будущий RFC3339 timestamp для синхронного старта.

Portable package включает этот же `README.md` как главный manual. Отдельный полный `README_RU.md` или `PORTABLE_RU.md` не используется как основная инструкция.

## 8. Known limitations

- Go loadgen создает protocol/engine load, а не browser UI load.
- Массовое тестирование реальных browser/Web Listener клиентов — отдельная задача.
- Transport может требовать server-side log correlation, если loadgen не может напрямую и надежно наблюдать selected ICE pair.
- Цель 2000 listener остается future work и направлением масштабирования, а не требованием MVP.
