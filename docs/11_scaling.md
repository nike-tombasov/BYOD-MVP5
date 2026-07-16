## 11. System scaling

1 room = 1 VPS (арендуемая мощность зависит от планируемой конференции) 

`target_capacity` definition:
- planned target number of conference participants (listeners) for one room/VPS sizing;
- entered by admin during deploy together with room data;
- immutable during event runtime (until next deploy/reconfiguration cycle).
- derived limits (`max_active_listeners`, `max_new_connections_per_sec`) are calculated once in backend from `target_capacity` and remain fixed until event end.

Ожидаемые пределы на 1 VPS (не должно быть предограничением системы):
* 500-3000 users
* до 32 channels
* до 32 Publishers

В средняя ожидаемая реальная нагрузка на 1 VPS:
* 100-200 users
* 2-5 channels

Максимальная ожидаемая нагрузка на 1 Publisher (не должно быть предограничением системы): 32 channels

Средняя ожидаемая нагрузка на 1 Publisher: 2-5 channels

## 11.1. Listener admission control baseline (MVP Stage VII-IX)

Recommended baseline formulas:
- `max_active_listeners = target_capacity * 1.05`
- `max_new_connections_per_sec = max(1, target_capacity / 15)`
- `listener_min_reconnect_interval_per_ip_seconds = 2`

Admission-control meanings:
- `max_new_connections_per_sec` is a global backend Listener admission rate.
- `listener_min_reconnect_interval_per_ip_seconds` is a per-IP Listener
  connect/reconnect throttle.
- In NAT/public Wi-Fi/hotel networks, many real users may share one public IP.
- These two limits can stack: global new Listener connection rate plus per-IP
  connect/reconnect interval.
- This is intentional protection, but it must be adjustable for stress tests
  and event emergency operations.
- Important emergency/stress numbers are grouped in the top operator block of
  `src/backend/config.py`; edit the number and restart `byod-backend`.

Active PLAY heartbeat baseline:
- heartbeat interval = `10 sec`
- heartbeat timeout = `60 sec` -> reconnect required

## 11.2. Advanced load-control backlog (later stages)

- listener fingerprinting model
- NAT-aware admission control
- burst handling strategy
- proxy detection logic
- advanced rate-limit model
- reconnect SLA metrics
