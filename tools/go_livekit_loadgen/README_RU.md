# Go loadgen BYOD: Gate A (`backend-ws-only`)

Этот каталог содержит новый Windows-first Go loadgen для первой ступени нагрузочного тестирования BYOD. Gate A проверяет только backend WebSocket путь Listener: подключение к `/ws/listener`, обычный `connecting` envelope, backend heartbeat и удержание открытых WebSocket соединений во время HOLD. После получения `listener_state` loadgen выбирает первый канал с `listen=true` только для того, чтобы heartbeat соответствовал обычной backend семантике Listener.

## 1. Что проверяет Gate A

Gate A отвечает на вопрос: «Сколько Listener WebSocket подключений backend и путь до backend могут принять и удержать без LiveKit?»

Проверяются:

- backend endpoint `/ws/listener`;
- схема обычного Listener `connecting` сообщения;
- admission/reject логика backend;
- backend heartbeat протокол Listener с первым listenable каналом из `listener_state`;
- устойчивость WebSocket соединений во время HOLD;
- путь через nginx, если используется профиль `vps-nginx`.

## 2. Что Gate A не проверяет

Gate A не подключается к LiveKit и не проверяет медиа. Выбранный listenable канал используется только в backend heartbeat; это не браузерное воспроизведение и не LiveKit subscription.

Не проверяются:

- LiveKit join/connect;
- WebRTC ICE/UDP/TCP;
- подписка на аудио;
- RTP receive/discard;
- качество звука;
- CPU/память LiveKit под реальным media load.

Поэтому `transport_udp_tcp=n/a`: в Gate A LiveKit не используется.

## 3. Локальный запуск `local-direct`

Запускайте из каталога `tools/go_livekit_loadgen/` на Windows PowerShell:

```powershell
go run ./cmd/byod-loadgen `
  -profile local-direct `
  -mode backend-ws-only `
  -server http://127.0.0.1:8000 `
  -listeners 10 `
  -ramp-per-sec 5 `
  -hold-sec 60 `
  -runner-id win-dev-1 `
  -loadgen-key byod_loadgen_key_01
```

Профиль `local-direct` идёт напрямую в backend: `http://127.0.0.1:8000` превращается в `ws://127.0.0.1:8000/ws/listener`. Nginx для этого теста не нужен.

Можно также использовать helper:

```powershell
./scripts/run_backend_ws_local.ps1
```

## 4. Запуск через VPS/nginx `vps-nginx`

Запускайте из каталога `tools/go_livekit_loadgen/`:

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode backend-ws-only `
  -server http://<VPS_PUBLIC_IP_OR_DOMAIN> `
  -listeners 10 `
  -ramp-per-sec 5 `
  -hold-sec 60 `
  -runner-id win-home-1 `
  -loadgen-key byod_loadgen_key_01
```

Профиль `vps-nginx` идёт через nginx на тот же path `/ws/listener`. Этот тест помогает увидеть потолок nginx/WebSocket пути до backend, но всё ещё не проверяет LiveKit.

Helper:

```powershell
./scripts/run_backend_ws_vps.ps1 -Server http://<VPS_PUBLIC_IP_OR_DOMAIN>
```

## 5. Как стартовать безопасно

Не начинайте сразу с большого числа Listener. Увеличивайте нагрузку ступенями:

1. `10` listeners — smoke test, проверка запуска, JSONL/summary и базового протокола.
2. `50` listeners — малая нагрузка, проверка reject/error в live summary.
3. `100` listeners — первый реальный backend admission тест.
4. `500` listeners — stress run только после успешных меньших ступеней.

Для каждой ступени смотрите `backend_active`, `backend_rejected`, `backend_closed`, `heartbeat_failed` и итоговую классификацию run. HOLD начинается только после того, как ramp завершён и `backend_active` достиг `target_listeners`; одних накопленных successful connect недостаточно.

## 6. Что означают числа в live summary

Loadgen печатает одну короткую строку примерно раз в секунду:

- `ts_iso` — время по Москве `+03:00`, округлено до десятых секунды;
- `mode` — сейчас только `backend-ws-only`;
- `profile` — `local-direct` или `vps-nginx`;
- `target_listeners` — сколько активных Listener нужно набрать перед HOLD;
- `target_ws` — WebSocket URL, куда идёт тест;
- `started` — сколько worker goroutine стартовало;
- `backend_connected` — сколько Listener получили успешный backend state и выбрали listenable канал;
- `backend_active` — сколько workers сейчас удерживают активное backend WebSocket соединение;
- `backend_rejected` — сколько Listener получили backend error/reject;
- `backend_closed` — сколько соединений backend закрыл во время активного run;
- `heartbeat_ok` — сколько heartbeat сообщений успешно отправлено;
- `heartbeat_failed` — сколько heartbeat отправить не удалось;
- `ramp_done` — все запланированные workers уже стартовали;
- `hold_elapsed` — сколько секунд прошло в HOLD после достижения `backend_active >= target_listeners`;
- `errors_top` — самые частые ошибки;
- `transport_udp_tcp=n/a` — UDP/TCP не измеряется в Gate A, потому что LiveKit не используется.

## 7. `VALID_RUN`, `PARTIAL_RUN`, `INVALID_RUN`

Итоговый JSON summary содержит классификацию:

- `VALID_RUN` — target был активно удержан: `backend_active >= target_listeners` на старте HOLD, HOLD завершён, reject/close/heartbeat failure во время HOLD нет.
- `PARTIAL_RUN` — данные полезны, но target активных backend соединений или HOLD выполнены не полностью, либо были reject/close/error.
- `INVALID_RUN` — локальная настройка, протокол или логирование сломались так, что результату нельзя доверять.

## 8. Как распознать потолок nginx/WS

Для профиля `vps-nginx` возможный nginx/WebSocket ceiling выглядит так:

- `started` растёт, но `backend_active` не достигает `target_listeners`;
- `backend_closed` растёт во время HOLD;
- появляются handshake/connection reset/timeout ошибки в `errors_top`;
- локальный `local-direct` на той же мощности лучше, чем `vps-nginx`.

Если это происходит только через `vps-nginx`, смотрите nginx limits, worker connections, upstream timeouts и системные лимиты файловых дескрипторов. В рамках Gate A этот PR не меняет nginx config.

## 9. Как включить backend bypass перед stress run

Bypass нужен только для контролируемого stress run, когда много loadgen Listener идут с одного IP и могут упереться в per-IP `RECONNECT_TOO_FAST`.

На backend задайте env и перезапустите backend service:

```text
BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED=true
BYOD_LOADGEN_RECONNECT_BYPASS_KEY=byod_loadgen_key_01
```

Важно: bypass влияет только на `RECONNECT_TOO_FAST`. Он не отключает max active listeners, connection rate limit, schema validation, malformed messages или обычный Listener protocol.

## 10. Как выключить backend bypass после stress run

После теста удалите env overrides или явно поставьте:

```text
BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED=false
```

Затем перезапустите backend service и проверьте, что bypass выключен. Без включающего backend flag loadgen не получает никаких особых прав.

## 11. `loadgen_key` не является паролем

`loadgen_key` — это диагностический ключ для stress tooling, а не пароль и не секрет доступа. Он работает только если одновременно:

- backend-side enable flag включён;
- `loadgen_key` совпадает с backend config;
- metadata содержит `client_type: "load_runner"`;
- reject был именно `RECONNECT_TOO_FAST`.

Одного `client_type="load_runner"` недостаточно.

## 12. Где лежат результаты

По умолчанию результаты пишутся в `./out`:

- `events_<timestamp>.jsonl` — события workers в JSONL;
- `summary_<timestamp>.json` — итоговая сводка JSON.

Для другого каталога используйте `-out-dir`.

## Gate B: `livekit-connect-only`

Gate B добавляет к Gate A ещё один шаг: каждый Listener сначала проходит backend `/ws/listener`, получает backend-issued LiveKit token и `livekit_url`, выбирает первый listenable канал из `listener_state` для корректного backend heartbeat, а затем открывает LiveKit room signaling connection с этим token.

Gate B проверяет:

- backend WS admission path;
- выдачу LiveKit token/url backend-ом;
- способность LiveKit принять join/connect без подписки на media;
- удержание backend WS + LiveKit signaling connection во время HOLD.

Gate B не проверяет:

- audio playback;
- RTP receive/discard;
- browser rendering;
- качество звука;
- Gate C subscribe/discard media path.

Loadgen не генерирует token сам, не вызывает admin endpoints и не обходит backend admission. Gate B не публикует tracks, не подписывается на audio и не читает RTP.

### Local-direct пример

```powershell
go run ./cmd/byod-loadgen `
  -profile local-direct `
  -mode livekit-connect-only `
  -server http://127.0.0.1:8000 `
  -listeners 10 `
  -ramp-per-sec 5 `
  -hold-sec 60 `
  -runner-id win-dev-1 `
  -loadgen-key byod_loadgen_key_01
```

### VPS/nginx пример

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode livekit-connect-only `
  -server http://<VPS_PUBLIC_IP_OR_DOMAIN> `
  -listeners 100 `
  -ramp-per-sec 10 `
  -hold-sec 300 `
  -runner-id win-home-1 `
  -loadgen-key byod_loadgen_key_01
```

### Безопасная прогрессия Gate B

Идите ступенями: `10 → 50 → 100 → 500`. Переходите к следующей ступени только если предыдущая даёт `VALID_RUN` или понятный `PARTIAL_RUN` без системного потолка.

### Gate B live summary

- `backend_active` — сколько workers сейчас удерживают backend WebSocket.
- `livekit_connected` — сколько workers успешно открыли LiveKit signaling connection.
- `livekit_failed` — сколько workers не смогли подключиться к LiveKit или не получили нужные поля token/url.
- `livekit_disconnected` — сколько LiveKit connections закрылись во время run.
- `transport_udp`, `transport_tcp`, `transport_unknown` — best-effort транспортная диагностика. В этом PR транспорт может быть `unknown`, если точный selected ICE candidate недоступен в текущем connect-only пути.
- `udp_tcp_ratio` — диагностическое число, а не pass/fail само по себе. Нельзя фейкать UDP/TCP: если транспорт неизвестен, он считается как `transport_unknown`.

`VALID_RUN` для Gate B означает, что target workers стартовали, backend active target достигнут, LiveKit active target достигнут, HOLD завершён, не было backend reject, LiveKit disconnect во время HOLD и heartbeat failures во время HOLD.

## Gate C: `livekit-subscribe-discard-rtp`

Gate C расширяет Gate B: Listener проходит backend, получает token/url, подключается к LiveKit через SDK, подписывается на audio tracks и читает RTP packets, но сразу отбрасывает их.

Gate C проверяет:

- backend WS admission и heartbeat;
- LiveKit room connect;
- подписку на audio track;
- получение RTP packets без декодирования;
- удержание backend + LiveKit + media receive path во время HOLD.

Gate C не делает:

- audio decode;
- playback через speakers/headphones;
- использование microphone/audio devices;
- publish tracks;
- проверку качества звука.

Перед Gate C должен быть активен Publisher. Без активного Publisher и audio track Gate C обычно даст `PARTIAL_RUN` с `workers_without_audio_track` / `worker_no_audio_track_timeout`.

Пример VPS/nginx:

```powershell
go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode livekit-subscribe-discard-rtp `
  -server http://<VPS_PUBLIC_IP_OR_DOMAIN> `
  -listeners 100 `
  -ramp-per-sec 10 `
  -hold-sec 300 `
  -runner-id win-home-1 `
  -loadgen-key byod_loadgen_key_01
```

Безопасная прогрессия Gate C: `1 → 5 → 10 → 50 → 100 → 500`. Начинайте с `1`, чтобы убедиться, что Publisher active и RTP packets реально приходят.

Счётчики Gate C:

- `audio_tracks_subscribed` — сколько audio track subscription events увидел loadgen;
- `workers_with_audio_track` — сколько workers получили audio track;
- `workers_without_audio_track` — сколько active LiveKit workers ещё без audio track;
- `rtp_packets` — сколько RTP packets прочитано и отброшено;
- `rtp_bytes` — оценка bytes для отброшенных RTP packets;
- `rtp_read_errors` — ошибки чтения RTP;
- `transport_udp/tcp/unknown` и `udp_tcp_ratio` остаются best-effort diagnostics; UDP/TCP может быть `unknown`, пока не добавлены transport stats.

`VALID_RUN` для Gate C требует backend target, LiveKit target, audio track target, HOLD completion и отсутствие backend/LiveKit/heartbeat/RTP failures during HOLD.
