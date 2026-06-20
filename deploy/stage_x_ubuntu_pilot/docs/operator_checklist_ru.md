# PR43: nginx/backend capacity checklist

Короткий чеклист для оператора после установки PR43 на single-purpose BYOD VPS.

## 1. Запустить smoke test

```bash
cd /opt/byod/app-src
sudo bash deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh
```

Ожидаемый формат — одна строка на сервис/проверку:

- `backend: active, health=ok, port=8000-listening` — backend запущен, локальный `/health` отвечает, порт 8000 слушает только локально.
- `nginx: active, config=ok, worker_connections=65535, nofile=200000` — nginx запущен, конфиг валиден, поднят лимит WebSocket/FD.
- `livekit: active, port=7880-listening, tcp=7881-listening` — LiveKit запущен, основные TCP ports слушают.
- `btop: installed` — операторский мониторинг установлен.
- `vendor/livekit-client: present|missing` — локальный pinned browser SDK для Listener найден или отсутствует.
- `metrics: local-only-ok|unavailable` — backend metrics доступны локально на `127.0.0.1:8000` или недоступны.

Smoke test не должен печатать длинные логи по умолчанию. Если backend, nginx или LiveKit явно неактивны, smoke test завершится с ошибкой.

## 2. Проверить nginx limits вручную

```bash
sudo nginx -t
sudo nginx -T | grep -E 'worker_processes|worker_connections|worker_rlimit_nofile'
```

Нужно увидеть примерно:

```text
worker_processes auto;
worker_rlimit_nofile 200000;
worker_connections 65535;
```

## 3. Проверить systemd file descriptor limits

```bash
systemctl show nginx -p LimitNOFILE
systemctl show byod-backend -p LimitNOFILE
```

Ожидаемо:

```text
LimitNOFILE=200000
```

## 4. Посмотреть текущие TCP соединения

```bash
sudo ss -tanp | grep nginx | wc -l
sudo ss -tanp | grep ':8000' | wc -l
```

Эти числа помогают понять, сколько соединений держит nginx и сколько upstream/backend соединений видно на порту 8000. Для proxied WebSocket nginx держит клиентскую и upstream сторону, поэтому nginx connections растут быстрее, чем число Listener.

## 5. Запустить Gate A после PR43

Gate A берётся из Go loadgen PR42. Запускайте с Windows/operator machine из `tools/go_livekit_loadgen/`.

Пример через nginx/VPS:

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

Безопасная прогрессия:

1. `10` listeners — smoke.
2. `50` listeners — малая нагрузка.
3. `100` listeners — проверка устойчивости.
4. `500` listeners — целевой PR43 check для nginx/backend path.

Этот PR всё ещё не тестирует LiveKit, audio, RTP, UDP/TCP media или browser playback. Gate A проверяет только backend WebSocket path и capacity nginx/backend соединений.

## 6. Если снова появляется потолок около ~382

Повторяющийся ceiling около 382 Listener обычно означает, что nginx или systemd file descriptor/connection limits всё ещё применяются не из нового конфига, либо сервис не был перезапущен после установки override.

Проверьте:

```bash
sudo nginx -t
sudo nginx -T | grep -E 'worker_processes|worker_connections|worker_rlimit_nofile'
systemctl show nginx -p LimitNOFILE
systemctl show byod-backend -p LimitNOFILE
sudo ss -tanp | grep nginx | wc -l
sudo ss -tanp | grep ':8000' | wc -l
```

## 7. Что собрать, если тест всё ещё зависает

Сохраните и передайте:

- вывод `50_smoke_test.sh`;
- вывод команд из раздела 6;
- последние строки `journalctl -u nginx -u byod-backend -u byod-livekit --no-pager -n 200`;
- JSON summary и JSONL events из Go Gate A `out/`;
- `sudo bash deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh` и путь к созданному `/tmp/byod-diagnostics-<timestamp>/`.
