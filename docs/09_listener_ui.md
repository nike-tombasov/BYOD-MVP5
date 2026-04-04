## 10. Listener Web UI (HTML)

### 10.1. Внешний вид. 

User должен иметь минимальный интерфейс. Блоки:

1) room_status в виде красного поля сверху с белым status custom text (исчезает при OPENED)
2) заголовок - room_name
3) channel list в виде БОЛЬШИХ button, расположенных сверху вниз

“CONNECT” button не требуется.

### 10.2. Путь listener

0) открытие web page (landing)
1) отображение заглушки, логотипа, welcome text до получения актуальных room data
2) автоматическое получение от backend JWT token Identity listener_id
3) автоматическое получение от backend channel list
4) отображение/generation status custom text (при status OPENED ничего не отображать) room_name, отображение channel buttons с режимом listen == true
5) нажатие на желаемый channel button (play action), button меняет цвет (подсвечивается), автоматизированное воспроизведение звука только по этому channel даже если Publisher ещё не появился
6) channel button не меняет цвет (не гаснет) за исключением перезапуска web page, перевода в room status CLOSED
7) нажатие другой channel button (stop action для предыдущего channel и play action для нового channel), предыдущая channel button меняет цвет обратно (гаснет), новая меняет цвет (подсвечивается)
8) нажатие на active channel button (stop action для текущего воспроизведения channel), кнопка меняет цвет обратно (гаснет)
9) heartbeats, горячее изменение channel names от backend, появление channel buttons при переводе channels listen в true (не должно влиять на active play, по которому уже нажата channel button)

### 10.3 Listener playback algorithm

ON CHANNEL BUTTON CLICK:

if same channel:
    pause audio
    detach track from audio element
    clear state

else:
    detach previous track
    find trackPublication by track.name == channel_id
    setSubscribed(true)
    attach track to audio element
    audio.play()

### 10.4. Existing tracks handling

After connecting to LiveKit room, Listener MUST:

- iterate over room.remoteParticipants
- iterate over participant.trackPublications
- detect already published tracks (trackName == channel_id)
- store references to these tracks

Listener MUST NOT rely only on trackSubscribed event.

### 10.5. Detach audio element rules

When switching or stopping channel:

Listener MUST:
- call audio.pause()
- set audio.srcObject = null
- clear reference to current track

If this is not done, browser will continue playback.

### 10.6. Key technologies

- autoSubscribe = false
- selective subscribe
- autoplay (только после нажатия на channel button, не работает после stop action)
- НЕ создавать новый audio element каждый раз (используется только один audio element на протяжении всей сессии, при смене channel выполняется detach предыдущего channel и attach нового).
- обмен данным с backend по WebSocket 
- автоопределение users system language (если не известен - English)
- users system volume control для динамиков/наушников
- active with blocked screen on mobile
- users system mobile player (includes only pause/play button) 
- бесшовное получение JWT token на замену истёкшему, звук не пропадает и не обрывается
- jitter buffer, packet recovery (при плохом Wi-Fi, 3G/LTE - в будущем)
- reconnection при перезагрузке VPS (в будущем)

### 10.7. Поведение. Важные моменты

NOT subscribe на всё. Listener subscribe на LiveKit track, имя которого равно выбранному channel_id.

При смене publisher LiveKit автоматически отправляет события: trackUnsubscribed → trackSubscribed, что обеспечивает автоматическое восстановление аудио.

Idle, если не выбран ни один channel (no channel button pushed) - user никакой звук не получает, listener NOT subscribe ни на один трек!

При нажатии на channel button запускается selectedTrack и в следствии - selective subscribe, Autoplay, audio element.

Звук не должен появляться сам ни при открытии страницы, ни на уже открытой странице из-за появления новых Publisher, новых publish track.

Если user нажал channel button и она горит (channel play action), то ему приходит звук только соответствующего channel, никакой другой звук и track приходить не должен!

Нажатая channel button отжимается (stop action) либо вручную by user, либо перезагрузкой web страницы, либо by room status CLOSED.