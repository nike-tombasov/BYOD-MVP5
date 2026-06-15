# Stage X: руководство по smoke test

Запускайте smoke test после deploy, изменения конфигурации или обслуживания
VPS. Целевая среда: Ubuntu Server 22.04 LTS, один VPS с public IPv4.

## A. Что проверяет smoke test

- что nginx, `byod-backend` и `byod-livekit` запущены через systemd;
- что ожидаемые порты слушаются правильными процессами;
- что backend health доступен локально и через nginx;
- что статические файлы Listener доступны пользователю `www-data`;
- что Listener и Publisher проходят базовый end-to-end сценарий;
- что LiveKit принимает соединения и передаёт audio;
- что operator может найти service logs и собрать diagnostic bundle.

Smoke test подтверждает базовую работоспособность после deploy. Он не заменяет
acceptance test или нагрузочный тест.

## B. Что smoke test не проверяет

- Protocol/engine load и максимальную Listener capacity;
- Browser/Web Listener UI load;
- длительную стабильность и поведение при деградации;
- production TLS/domain, load balancer или multi-node setup;
- полную security audit;
- все network paths и browser combinations.

Stage XI нагрузка описана отдельно в `docs/22_stress_tests.md`.

## C. Быстрая проверка сервисов

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager -l
sudo systemctl status byod-backend --no-pager -l
sudo systemctl status byod-livekit --no-pager -l
```

Ожидается `active (running)` у трёх сервисов и успешный `nginx -t`. Если сервис
неактивен, сначала изучите его journal, а не перезапускайте всё вслепую.

## D. Проверка портов

```bash
sudo ss -lntup | grep -E ':(80|8000|7880|7881)\b'
```

Ожидается:

- nginx на `:80`;
- backend только на loopback `127.0.0.1:8000`, не на public interface;
- LiveKit на `:7880` и `:7881`.

Provider firewall должен разрешать inbound `80/tcp`, `7880/tcp`, `7881/tcp` и
`50000-50100/udp`. Порт `8000/tcp` нельзя открывать наружу.

## E. Проверка backend через nginx

```bash
curl -i http://127.0.0.1/health
curl -i http://<VPS_PUBLIC_IP>/health
```

Оба запроса должны вернуть успешный health response. Первый проверяет локальный
nginx path, второй — public IPv4 path. Не подставляйте token, PIN или иные
секреты в команду.

Для проверки конфигурационных файлов и видимых управляющих символов:

```bash
sudo sed -n '1,160l' /opt/byod/config/backend.env
sudo sed -n '1,160l' /opt/byod/config/livekit.yaml
```

Если файлы были перенесены с Windows и обнаружен CRLF, удалите `\r`:

```bash
sudo sed -i 's/\r$//' /opt/byod/config/backend.env
sudo sed -i 's/\r$//' /opt/byod/config/livekit.yaml
```

После изменения конфигурации выполните restart соответствующих сервисов.

## F. Проверка Listener

Проверьте права чтения обязательных файлов:

```bash
sudo -u www-data test -r /opt/byod/listener/index.html && echo OK || echo FAIL
sudo -u www-data test -r /opt/byod/listener/listener.js && echo OK || echo FAIL
sudo -u www-data test -r /opt/byod/listener/vendor/livekit-client.umd.1.15.13.js && echo OK || echo FAIL
```

Затем:

1. Откройте `http://<VPS_PUBLIC_IP>/` в поддерживаемом browser.
2. Убедитесь, что Listener автоматически подключается к
   `ws://<VPS_PUBLIC_IP>/ws/listener`.
3. Проверьте, что отображается room state и нет постоянного reconnect banner.
4. Выберите listenable channel.
5. При работающем Publisher подтвердите получение audio.

Query override `?backend=ws://...` используйте только как debug fallback.
Pinned local Listener Web SDK должен оставаться версией `1.15.13`.

## G. Проверка Publisher

1. Запустите штатный Publisher на Windows 10/11.
2. Укажите public IPv4 VPS и используйте разрешённый тестовый PIN, не записывая
   его в документацию или diagnostic bundle.
3. Подтвердите backend WebSocket connection и успешное LiveKit connection.
4. Переведите канал в `ON AIR` и убедитесь, что публикуется правильный track.
5. На Listener выберите тот же канал и подтвердите audio.
6. Нажмите `STOP` и подтвердите штатное прекращение публикации.

Smoke test не меняет audio invariants: 48000 Hz, stereo, frame size 960,
`track.name == channel_id`, selective subscribe и queue drop-oldest.

## H. Проверка LiveKit

Проверьте статус и последние события:

```bash
sudo systemctl status byod-livekit --no-pager -l
sudo journalctl -u byod-livekit -n 120 --no-pager
```

Во время ручного Publisher/Listener сценария не должно быть устойчивых
`livekit_unreachable`, authentication failures или reconnect loop. Отдельный
мгновенный reconnect ещё не доказывает отказ VPS — сопоставьте время с backend
и nginx logs.

## I. Где смотреть логи

```bash
sudo journalctl -u byod-backend -n 120 --no-pager
sudo journalctl -u byod-livekit -n 120 --no-pager
sudo journalctl -u nginx -n 120 --no-pager
sudo tail -n 80 /opt/byod/backend_data/connections_log_$(date -u +%Y%m%d).jsonl
sudo tail -n 80 /opt/byod/backend_data/events_log_$(date -u +%Y%m%d).jsonl
```

Сопоставляйте timestamps между журналами. Не публикуйте логи без проверки на
IP, token, PIN и другие чувствительные данные.

## J. Полный cold restart BYOD stack

Для последовательного restart работающего stack:

```bash
sudo systemctl restart byod-livekit
sudo systemctl restart byod-backend
sudo systemctl restart nginx
```

После этого повторите разделы C–H. Это restart, а не полная остановка питания
VPS.

## K. Полная остановка BYOD stack

```bash
sudo systemctl stop byod-backend
sudo systemctl stop byod-livekit
sudo systemctl stop nginx
```

Команда прервёт текущие Listener и Publisher sessions и сделает public HTTP
недоступным. Используйте только в согласованное окно обслуживания.

## L. Полный запуск BYOD stack

```bash
sudo systemctl start nginx
sudo systemctl start byod-livekit
sudo systemctl start byod-backend
```

После запуска обязательно проверьте status, ports и health. Порядок здесь
предназначен для запуска полностью остановленного stack.

## M. Restart отдельных сервисов

```bash
sudo systemctl restart nginx
sudo systemctl restart byod-backend
sudo systemctl restart byod-livekit
```

Выполняйте только нужную строку. Restart nginx кратко влияет на HTTP/WebSocket,
restart backend разрывает backend sessions, restart LiveKit разрывает WebRTC
sessions.

## N. Diagnostic bundle

```bash
sudo bash deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh
```

Перед передачей bundle третьим лицам проверьте его на credentials, tokens,
реальные PIN, private keys и персональные/IP данные. Diagnostic bundle помогает
расследованию, но не заменяет live service status и journal.

## O. Dangerous commands

Следующие команды **не являются smoke test**. Не запускайте их для обычной
диагностики:

```bash
sudo rm -rf /opt/byod
sudo ufw reset
sudo systemctl disable nginx
sudo systemctl disable byod-backend
sudo systemctl disable byod-livekit
sudo truncate -s 0 /opt/byod/config/backend.env
sudo truncate -s 0 /opt/byod/config/livekit.yaml
sudo reboot
sudo poweroff
```

Почему это опасно:

- `rm -rf /opt/byod` необратимо удаляет приложение, конфигурацию, данные и
  локальные логи.
- `ufw reset` сбрасывает firewall policy и может одновременно закрыть
  административный доступ или открыть нежелательные пути после новой настройки.
- `systemctl disable ...` убирает autostart. После reboot stack может не
  подняться, даже если ручной `start` раньше работал.
- `truncate -s 0 ...` полностью обнуляет конфигурацию backend или LiveKit;
  восстановление потребует корректной резервной копии.
- `reboot` завершает все sessions и перезапускает VPS.
- `poweroff` выключает VPS и может потребовать запуска через панель provider.

Перед destructive action зафиксируйте причину, сделайте backup и убедитесь, что
у вас есть доступ к provider console и проверенная процедура восстановления.
