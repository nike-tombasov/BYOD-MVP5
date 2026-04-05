## 10. Listener Web UI (HTML)

### 10.1. Внешний вид. 

User должен иметь минимальный интерфейс. Блоки:

1) room_status в виде красного поля сверху с белым status custom text (исчезает при OPENED)
2) заголовок - room_name
3) channel list в виде БОЛЬШИХ button, расположенных сверху вниз

“CONNECT” button не требуется.

### 10.2. Путь listener UI

0) открытие web page (landing)
1) отображение заглушки, логотипа, welcome text до получения актуальных room data
2) автоматическое получение от backend JWT token Identity listener_id
3) автоматическое получение от backend channel list
4) initialize generation with status custom text (при status OPENED ничего не отображать), room_name, отображение channel buttons с режимом listen == true
5) нажатие на желаемый channel button (PLAY ACTION), button меняет цвет (подсвечивается), автоматическая обработка получения звука только по этому channel
6) channel button не меняет цвет (не гаснет) за исключением перезапуска web page, перевода room status в CLOSED
7) нажатие другого channel button (STOP ACTION для предыдущего channel и PLAY ACTION для нового channel) - предыдущая channel button меняет цвет обратно (гаснет), новая меняет цвет (подсвечивается) - звук с предыдущего channel button прекращает поступать для user, поступает только звук с новго channel button
8) нажатие на current channel button (STOP ACTION для текущего воспроизведения channel), channel button меняет цвет обратно (гаснет), звук перестаёт поступать для user
9) heartbeats, горячее изменение channel names от backend
10) появление скрытых channel buttons при переводе channels listen в true - не должно влиять на нажатый current channel button, прослушивание канала не должно оборваться

### 10.3. LISTENER STATE MACHINE

Listener playback states:

IDLE
- no button pressed
- no track attached
- audio paused

WAITING
- button pressed
- track not yet available
- waiting for trackSubscribed

PLAYING
- PLAY ACTION executed
- track attached
- audio playing

STOPPED
- STOP ACTION executed
- detached
- return to IDLE

Transitions:

IDLE -> WAITING (button click, no track)
IDLE -> PLAYING (button click, track exists)

WAITING -> PLAYING (trackSubscribed)
WAITING -> IDLE (current channel button click - STOP ACTION)

PLAYING -> WAITING (trackUnsubscribed)
PLAYING -> IDLE (current channel button click - STOP ACTION)

### 10.4. Listener playback algorithms (PLAY and STOP ACTION)

Listener playback state is controlled ONLY by one current button
If button pressed and track not yet published: Listener enters WAITING state for LiveKit event.

ON CHANNEL BUTTON CLICK:
```
if same channel:
    STOP ACTION
else:
    WAITING or PLAY ACTION
```

PLAY ACTION:
```
    STOP ACTION
    ATTACH ACTION
```

STOP ACTION:
```
    pause audio
    detach current track from audio element
    clear srcObject
    optionally call setSubscribed(false)
    clear state (IDLE)
```

ATTACH ACTION:
```
    wait until complete detaching previous track
    find publication
    setSubscribed(true)
    attach track to audio element
    audio.play()
```

On trackSubscribed:
```
if state == WAITING and publication.trackName == currentChannel:
    ATTACH ACTION
    state = PLAYING
```

On trackUnsubscribed:
```
if unsubscribed track == currentTrack
    state = WAITING
```

Hiding channels:
```
if current channel sets listen = false:
    STOP ACTION
```
### 10.5. Existing tracks handling

Naming rule:
- publication.trackName (or track.name) MUST be exactly channel_id.
- currentChannel in Listener logic means selected channel_id from pressed button.


After connecting to LiveKit room, Listener MUST:
- iterate over room.remoteParticipants
- iterate over participant.trackPublications
- detect already published tracks (trackName == channel_id)
- store references to these tracks

Listener MUST NOT rely only on trackSubscribed event.

If setSubscribed(true) is sent but trackSubscribed event is delayed/missed, Listener should retry publication check for currentChannel for short timeout window (e.g. 2-3s) and attach as soon as publication.track appears.

When detecting existing track after connect:
```
if state == WAITING and trackName == currentChannel:
    ATTACH ACTION
    state = PLAYING
```

### 10.6. Attaching and detaching audio element rules

Detach must complete synchronously before new attach.
No parallel attach allowed.

If track already attached -> ignore duplicate.

Ignore clicks while detach in progress (detachInProgress flag). Ignore clicks while attach in progress (attachInProgress flag).

Attach/detach operations MUST have timeout (e.g. 1000 ms). If timeout reached:
```
    reset state to IDLE
    allow new clicks
```

When switching or stopping channel Listener MUST:
- call audio.pause()
- set audio.srcObject = null
- clear reference to current track

If this is not done, browser will continue playback.

### 10.7. Key technologies

- autoSubscribe = false
- selective subscribe
- autoplay (только после нажатия на channel button; после STOP ACTION повторное нажатие channel button снова запускает звук)
- НЕ создавать новый audio element каждый раз (используется только один audio element на протяжении всей сессии, при смене channel выполняется detach предыдущего track и attach нового).
- обмен данным с backend по WebSocket 
- автоопределение users system language (если не известен - English)
- users system volume control для динамиков/наушников
- active with blocked screen on mobile
- users system mobile player (includes only pause/play button) 
- бесшовное получение JWT token на замену истёкшему, звук не пропадает и не обрывается
- jitter buffer, packet recovery (при плохом Wi-Fi, 3G/LTE - в будущем)
- reconnection при перезагрузке VPS (в будущем)

### 10.8. Поведение. Важные моменты

* NOT subscribe на всё. Listener subscribe на LiveKit track, имя которого равно выбранному channel_id.
* При смене publisher LiveKit автоматически отправляет события: trackUnsubscribed → trackSubscribed, что обеспечивает автоматическое восстановление аудио.
* Idle, если не выбран ни один channel (no channel button pushed) - user никакой звук не получает, listener NOT subscribe ни на один трек!
* При нажатии на channel button запускается selectedTrack и в следствии - selective subscribe, Autoplay, audio element.
* Звук не должен появляться сам ни при открытии страницы, ни на уже открытой странице из-за появления новых Publisher, новых publish track.
* Если user нажал channel button и она горит (current channel PLAY ACTION), то ему приходит звук только по current channel, никакой другой звук и track приходить не должен!
* Нажатая channel button отжимается/гаснет (STOP ACTION) либо вручную by user, либо перезагрузкой web страницы, либо by room status CLOSED.
* Listener MUST NOT rely only on trackSubscribed
* Listener MUST check existing publications after connect
* Listener uses button as the only trigger for playback - PLAY ACTION, STOP ACTION