## 3. Main system roles

### 3.1 Publisher (room technician)

LiveKit Identity - publisher

Функции:
* подключение к серверу VPS - ввод IP и ввод PIN комнаты
* автополучение LiveKit token
* выбор audio device (внешних или виртуальных аудиокабелей)
* publishes track and start stream by ON AIR button
* мониторинг индикации звука

Room technician не управляет и не видит users. Room technician может иметь на один room/hall как несколько PC, в каждый из которых поступает one or more channels, так и один PC, в котором также оцифрованы все звуковые channels одновременно.

### 3.2 Backend (room admin)

Backend на VPS выполняет:
* PIN verification
* token generation
* выдачу channels configuration  (в т.ч. room_name, channel_label) с возможностью изменений "налету"
* room управление (в т.ч. blocked, opened, closed statuses)
* защиту доступа (в т.ч. статистика, визуализация состояния по логам)
* резервную channel multi-track recording

### 3.3 Listener (users landing)

LiveKit Identity - listener

User:
* открывает web page
* автоматически room connect
* автоматически receive token
* выбирает channel из vertical list in button view
* hearing stream, при желании pressing button for stop/pause hearing

No user authorization required.
