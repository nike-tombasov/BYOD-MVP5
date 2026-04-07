## 8. Publisher UI

### 8.1. Сценарии использования в комнате:

* один PC - один Publisher - один и более streaming channel
* несколько PC - один Publisher на каждом PC - один канал стриминга на каждом PC (без единовременного пересечения)
* несколько PC - один Publisher на каждом PC - более одного канала стриминга на каждом (без единовременного пересечения)

Interlock применяется только на уровне channel_id.
One Publisher can stream multiple channels.

### 8.2. Структура интерфейса (по блокам):

1) Подключение к VPS - подписи и поля ввода IP и PIN, кнопка CONNECT, статус подключения к backend 
2) Room info (поступает от backend динамически) - room_name, room_status
3) Channels (поступают от backend динамически), где в каждом подблоке строки:
- 3.1) channel_id, channel_label  
- 3.2) выпадающий список audio device, ON AIR button
- 3.3) UI channel status, sound status (посредством RMS анализатора)

### 8.3. Модуль RMS analyzer

RMS analyzer работает постоянно.

Функции:
* проверка наличия сигнала
* обновление статуса
* диагностика

RMS вычисляется:
sqrt(mean(square(audio)))

Статусы:
* SOUND OK
* NO SOUND

Частота RMS analyzing. RMS analyze: каждый аудио блок

UI может обновляться реже.

Планируемые визуальные индикаторы (не критичны для MVP):
* VU meter
* RMS meter
* audio level bars

### 8.4. Модуль AudioStream

Компонент capture audio.

Функции:
capture audio
↓
RMS analysis
↓
enqueue frames
↓
send to LiveKit engine

Использует:
sounddevice.InputStream

Publisher получает device list через:
sounddevice.query_devices()

Форма отображения:
НАЗВАНИЕ | Device sample rate | Number of channels

Фильтрация устройств:
* only input devices
* only WASAPI
* исключение системных устройств

Если устройство mono, то программно дублировать в duble mono (pseudostereo).
Если устройство multi-channel, то программно cut channels upper 2.

### 8.5. Путь Publisher

0) доступен блок подключения к серверу, остальные блоки не заполнены
1) room technician вводит IP+PIN, нажимает CONNECT button
2) статус в блоке подключения меняется на Connecting..., в backend отправляются IP+PIN и Windows system hostname (backend проверяет правильность room PIN, generate and send в ответ JWT token Identity publisher_id и персональный publisher_id)
3) блок подключения к серверу отображает статус Connected при успешном подключении, кнопка CONNECT становится неактивной/некликабельной, а в случае обрывов выводить статус CONNECTION ERROR или Invalid PIN в случае неверного PIN
4) получает room info from backend (поля заполняются автоматически) в динамическом режиме - room_name, room_status, channel_id, channel_label, а также owner по каждому channel_id
5) room technician выбирает audio device в выпадающих списках по каждому channel, планируемым to stream
6) room technician самостоятельно убеждается, что нет sample rate ошибки и RMS analyzer показывает наличие звука
7) room technician нажимает по подготовленным channels ON AIR button (UI channel status меняется на Connecting...) и самостоятельно убеждается, что нет device error, ожидает подтверждения от backend
8) backend регистрирует owner и рассылает актуальный state
9) если owner == self publisher_id, то publishes track and start sending frames, and room technician самостоятельно убеждается, что UI channel status сменился на STREAMING
10) автоматическая отработка Heartbeats
11) room technician нажимает STOP button по тем channels, где publish\stream больше не требуется
12) room technician визуально контролирует состояние звука (RMS analyzer) и статуса соединений (server connection, room and streaming channels)
13) в случае ошибок или необходимости сменить room - закрывает и запускает Publisher заново
14) при завершении работы может просто закрыть Publisher UI (без необходимости STOP streaming)
15) backend регистрирует owner == null при получении STOP from Publisher по конкретному channel_id (или закрытии Publisher UI) и рассылает актуальный state, status channel_id меняется на FREE

### 8.6. Блок IP+PIN

Publisher UI хранит последнюю введённую комбинацию IP+PIN и подставляет при последующем открытии

Статусы (цвет):
* IDLE (чёрный)
* Connecting... (жёлтый)
* CONNECTED (зелёный)
* CONNECTION ERROR (красный)
* Invalid PIN (красный)

Entering Publisher into the room никак не нарушает работу других Publishers, в том числе которые уже ON AIR

При наличии связи с сервером CONNECT button должна быть неактивной/некликабельной для защиты от случайного повторного подключения. Room technician перезапускает Publisher UI при необходимости сменить room

### 8.7. Блок ROOM

Динамически расширяющееся поля для текста в случае громоздких названий
room_status никак не влияет на работу Publisher

Статусы (цвета):
* OPENED (зелёный)
* BLOCKED (жёлтый)
* CLOSED (красный, моргающий 500мс)

### 8.8. Блок CHANNELS


До CONNECT:
- channel_label = N/A
- room_name и room_status пустые
- ON AIR buttons disabled
- audio device dropdown disabled

После CONNECT отображаются только channel_id, пришедшие от backend state. Неиспользуемые channel_id скрываются из UI.
Publisher UI для Stage V строится сразу на 32 channel_id (channel_0...channel_31). Окно фиксированного размера, блок channels работает через vertical scroll.

Колесо мыши по device dropdown без раскрытия списка отключено специально (защита от случайной смены устройства при большом числе channels).

При заполнении блока channels в момент подключения к комнате ни один audio device выбран быть не должен. По умолчанию отображается служебный пункт None.

Кнопка ON AIR по умолчанию серая, после STOP streaming  - серая. При audio device == None кнопка ON AIR disabled (как и при samplerate error), backend ON AIR request не отправляется. NO DEVICE можно показать при наведении мыши на disabled ON AIR кнопку (подсказка room technician).

UI channel status отрабатываются внутри Publisher UI на основании state от backend и прочих внутренних состояний.

UI channel statuses (цвета):
* FREE (зелёный)
* Connecting... (жёлтый)
* STREAMING (чёрный)
* NO DEVICE (красный)
* ENGAGED (красный)
* DEVICE ERROR (красный)
* Device error. Check system samplerate (48000 Hz only) (красный)

UI channel status “Device error. Check system samplerate (48000 Hz only)” отображается сразу в момент выбора соответствующего audio device из списка. При выборе audio device с samplerate 48000 ошибка исчезает сразу и UI channel status меняется на актуальный.

При samplerate != 48000 кнопка ON AIR должна быть неактивной, backend запрос ON AIR отправлять запрещено.

* FREE отображается, если в backend owner == null
* STREAMING отображается, если в backend owner == self publisher_id
* NO DEVICE отображается в момент нажатия ON AIR button и если устройство не выбрано (None) (сменяется на актуальный UI channel status через 5 секунд)
* ENGAGED отображается, если в state от backend owner != self publisher_id
* DEVICE ERROR отображается в случае иных audio device ошибок
* Connecting... отображается сразу после нажатия на ON AIR button и до получения owner == self publisher_id, а также в процессе восстановления соединения после обрывов связи

### 8.9. Interlock логика, UI channel status ENGAGE и поведение ON AIR, STOP 

При нажатии на ON AIR button в backend отправляется связка информации о channel_id, publisher_id, on_air_ts. After push button сразу должна стать жёлтой, button label смениться на STOP. На время ожидания owner==self и во время STREAMING список audio devices по этому channel блокируется (no hot switching). Как только backend зарегистрировал channel_id owner, Publisher на основе полученного нового state (где owner == self publisher_id) publishes and start sending frames into LiveKit и меняет UI channel status на STREAMING, ON AIR button становится красной.

Другие room Publisher на основе полученного нового state (где owner != self publisher_id) меняют UI channel status на ENGAGED. Кнопка ON AIR становится не кликабельной, синего цвета.

При нажатии на STOP:

STOP
↓
stop sending frames
↓
unpublish track
↓
set UI channel status to Connecting…
↓
set ON AIR button label back to ON AIR (gray color)
↓
send stop to backend (channel_id, publisher_id, off_air_ts)
↓
backend owner = null
↓
backend send state
↓
publishers update UI
↓
publishers sets UI channel status FREE

### 8.10. Key technologies Publisher на Python:

- Разделение UI и асинхронной логики через отдельный event loop. asyncio запускается в отдельном threading.Thread, чтобы не блокировать PySide6 GUI.
- Передача аудио из callback в asyncio через asyncio.run_coroutine_threadsafe. Позволяет безопасно отправлять данные из аудио-потока (sounddevice) в async очередь.
- Использование asyncio.Queue как буфера между аудио захватом и LiveKit отправкой. Разрывает realtime callback и сетевую передачу, стабилизируя поток.
- Каждый трек имеет свой AudioSource, Queue, Stream.
- Во время ON AIR/handover список устройств блокируется. Смена устройства разрешена только при состоянии FREE/ENGAGED до нового ON AIR.
- Отдельный sender coroutine на каждый трек. asyncio.create_task(self.audio_sender(track)) обеспечивает независимую передачу.
- Минимизация latency через blocksize = 960. Это соответствует 20ms при 48kHz → стандарт для realtime WebRTC.
- Конвертация float audio → PCM16 перед отправкой. pcm16 = (data * 32767).astype(np.int16). Требуется LiveKit API.
- Thread-safe аудио захват через callback sounddevice.InputStream. Используется неблокирующий callback вместо polling.
- Ограничение размера очереди (maxsize=32). Предотвращает переполнение памяти и контролирует backpressure.
- Изоляция потоков: один device → один AudioStream объект. Управление через словарь self.streams[track].
- Проверка samplerate устройства перед стартом. Избегает resampling и лишней нагрузки CPU.
- UI сигнализация через Qt Signals (thread-safe обновления). UISignals.sound_update — безопасное обновление UI из async/threads.
- publish только при owner == self publiser_id после нажатия ON AIR.
- stop sending frames и unpublish при STOP.
- Audio queue overflow (нужно: drop oldest, non-blocking put)

### 8.11. Основные зависимости, использованные в Publisher UI v.0.2

* import sys 
* import time
* import asyncio 
* import threading 
* import numpy as np 
* import sounddevice as sd from PySide6.QtWidgets 
* import ( QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QHBoxLayout, QLineEdit ) from PySide6.QtCore 
* import Signal, QObject from livekit 
* import rtc from audio_stream 
* import sounddevice as sd

### 8.12. Visual specification Publisher UI (Stage V)

General:
- Theme: dark neutral background, no acid colors.
- Font: Segoe UI, fixed UI size (MVP fixed style).
- Status visibility enhancement: every status starts with colored square symbol "■".

Window and alignment:
- Start window width reduced to ~70% from previous v0.3 size.
- Button text alignment: centered.
- Main alignment: left-first, with stretch only where needed.

IP/PIN block:
- Row 1: `Server IP:` + address field + `PIN:` + PIN field + CONNECT button aligned right.
- CONNECT button width: by text appearance (no extra stretch width).
- Address and PIN fields: fixed width by practical symbol size.
- Row 2: connection status label aligned left.

Room block:
- Row 1: room_name on full available width with word-wrap.
- Row 2: room_status aligned left.

Channel block:
- Channel title row: left = `<id_without_channel_> - <channel_label>`, right = channel status.
- Channel controls row: audio device list + ON AIR button + RMS status.
- ON AIR button width: by text appearance.
- RMS status width: fixed by max text appearance (`SOUND OK` / `NO SOUND`).
- Thin light-gray horizontal separator between blocks/channels.

Color mapping (smooth palette):
- Connection statuses:
  - CONNECTED = green
  - Connecting... = yellow
  - CONNECTION ERROR / Invalid PIN = red
  - IDLE = blue/neutral
- Room statuses:
  - OPENED = green
  - BLOCKED = yellow
  - CLOSED = red
- Channel statuses:
  - FREE = green
  - Connecting... = yellow
  - STREAMING = green
  - ENGAGED = blue
  - NO DEVICE / DEVICE ERROR / samplerate error = red

Button palette:
- Default active and clickable: middle gray.
- Hover on enabled button: light gray.
- Disabled/blocked: dark gray.
- Pending ON AIR: yellow.
- Owner streaming (`STOP`): red.
- Engaged by another publisher: blue and disabled.

Interaction specifics:
- Mouse wheel scrolling on device dropdown without opening list is disabled.
- If device is NONE, ON AIR button is disabled.
- If samplerate != 48000, ON AIR button is disabled.
- NO DEVICE may be shown on mouse hover over disabled ON AIR button (NONE device case).
- After mouse leave from ON AIR button, temporary NO DEVICE hint must be reverted to last actual channel status immediately.
- After STOP flow and owner reset to null, button label must return to `ON AIR` immediately from state update.

Pre-connect and channel visibility:
- Before CONNECT:
  - room_name = empty
  - room_status = empty
  - channel_label = N/A
  - ON AIR disabled
  - device dropdown disabled
- After CONNECT:
  - only channels present in backend state are visible.
  - channels absent in backend state are hidden from UI.

### 8.13. Visual specification details (implemented values)

Typography and sizing:
- Base font family: `Segoe UI`.
- Base font size: `10 px`.
- Status square symbol `■`: `13 px`, `700` font-weight.
- ON AIR / STOP button padding: `4 px 10 px`.
- Input/dropdown internal padding: `3 px`.
- RMS label width: `88 px`.

Exact color palette (RGB):
- Main background: `rgb(38, 38, 38)` (`#262626`).
- Text color: `rgb(214, 214, 214)` (`#D6D6D6`).
- Horizontal separators: `rgb(255, 255, 255)` (`#FFFFFF`), thickness `2 px`.
- Input/dropdown field background: `rgb(51, 51, 51)` (`#333333`).
- Dropdown opened list background: `rgb(59, 59, 59)` (`#3B3B3B`).
- Hover on Dropdown opened list items: `rgb(179, 179, 179)` (`#B3B3B3`) with dark text.
- Dropdown border color: `rgb(85, 85, 85)` (`#555555`), thickness `2 px`.

Status colors:
- FREE / CONNECTED / OPENED: `rgb(143, 185, 150)` (`#8FB996`).
- Connecting... / BLOCKED: `rgb(201, 178, 106)` (`#C9B26A`).
- CONNECTION ERROR / Invalid PIN / NO DEVICE / DEVICE ERROR: `rgb(185, 122, 122)` (`#B97A7A`).
- ENGAGED (status + ON AIR engaged button): dark blue `rgb(31, 58, 95)` (`#1F3A5F`).

Button colors:
- Default active: `rgb(106, 106, 106)` (`#6A6A6A`).
- Hover on enabled buttons: `rgb(179, 179, 179)` (`#B3B3B3`) with dark text.
- Disabled: `rgb(74, 74, 74)` (`#4A4A4A`).
- Pending ON AIR: `rgb(167, 146, 86)` (`#A79256`).
- STOP (streaming): `rgb(168, 90, 90)` (`#A85A5A`).

Channel visibility:
- Non-present backend channels are fully hidden, including their bottom horizontal separators.


### 8.14. Token refresh and build mode decisions

Pinned decisions:
- Publisher refreshes token за 10 минут до expiry (MVP и production).
- MVP release artifact: folder build (`onedir`).
- Production target artifact: one-file build (`onefile`).
