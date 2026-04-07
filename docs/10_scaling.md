## 11. System scaling

1 room = 1 VPS (арендуемая мощность зависит от планируемой конференции) 

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
- `max_new_connections_per_sec = target_capacity / 15`
- `min_reconnect_interval_sec = 2+`

Active PLAY heartbeat baseline:
- heartbeat interval = `10 sec`
- heartbeat timeout = `60 sec` -> reconnect required
