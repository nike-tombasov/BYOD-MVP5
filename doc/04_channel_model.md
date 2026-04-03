## 5. Channel model 

Channels фиксированы по channel_id.

channel_0
channel_1
channel_2
...
channel_31

Максимум: 32 channels.

channel_label задаётся в backend, используется только для визуализации в UI (listener, publisher).

Всегда на последних channel_id создаются channel_label c названиями Reserve1, Reserve2 на стороне backend при разворачивании VPS.

Резервы во время конференции на стороне backend могут быть переименованы, обновлены в Publisher, отображены на сайте (лэндинге) у user.

channel_0 зарезервирован для:
- floor language
- original audio
- music
- main stage

channel_0 всегда создаётся при разворачивании VPS (по умолчанию должен быть скрыт/выкл)

Tracks creating in LiveKit only when publisher publishes.
Before publishing track отсутствует in room.

Очередь создаётся Publisher только после получения owner и перед publish.

queue is cleared on STOP.