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
4) automatic receive immutable `i18n_library` on connect/reconnect; initialize generation with status custom text (при status OPENED ничего не отображать), room_name, отображение channel buttons с режимом listen == true
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

Implementation priority note:
- это обязательный hardening-блок Stage IX (не переносить далее), т.к. rapid-click гонки приводят к недетерминированным переходам состояния.

### 10.7. Key technologies

- autoSubscribe = false
- selective subscribe
- autoplay (только после нажатия на channel button; после STOP ACTION повторное нажатие channel button снова запускает звук)
- НЕ создавать новый audio element каждый раз (используется только один audio element на протяжении всей сессии, при смене channel выполняется detach предыдущего track и attach нового).
- обмен данным с backend по WebSocket 
- автоопределение users system language (подробная спецификация: см. раздел 10.9)
- users system volume control для динамиков/наушников
- active with blocked screen on mobile
- users system mobile player (includes only pause/play button) 
- token lifecycle rules: см. docs/08_backend.md, раздел 9.2
- LiveKit JS SDK policy: pinned `1.15.13`.
- Local pinned file path (project): `src/listener/vendor/livekit-client.umd.1.15.13.js`.
- CDN source reference: `https://unpkg.com/livekit-client@1.15.13/dist/livekit-client.umd.js` (optional, future fallback discussion).
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

### 10.9. Спецификация автоопределения языка Listener UI (MVP)

Цель: помочь users на международных мероприятиях понимать:
- `room_name`
- `custom_status_text_blocked`
- `custom_status_text_closed`

Ключевая логика MVP:
1) Backend отправляет **все** языковые варианты текстов при initial connect и reconnect Listener по WebSocket.
1.1) Эти словари приходят как immutable `i18n_library` base payload (state-independent).
2) Backend **не получает** `ui_lang` и **не выбирает** язык за Listener.
3) Выбор языка выполняется только в Listener web page.
4) Status texts после deploy считаются фиксированными; изменение допускается только emergency override через manual console command (независимо для BLOCKED/CLOSED).

#### 10.9.1 Обязательные языки

Для каждого мероприятия обязательно подготовить минимум:
- English (`en`)
- Russian (`ru`)

Другие языки можно добавлять вручную до deploy.

#### 10.9.2 Языковые теги (официальный формат)

Использовать BCP 47 language tags:
- RFC 5646: https://datatracker.ietf.org/doc/html/rfc5646
- IANA Language Subtag Registry: https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry

Примеры: `en`, `en-US`, `ru`, `ru-RU`, `zh`, `zh-CN`.

#### 10.9.3 Формат данных и fallback на стороне Listener

Backend payload (образец): см. docs/08_backend.md, раздел 9.13.

Listener language selection rule:
```
detected = browser language (navigator.languages/navigator.language)
if i18n has exact tag:
    use exact tag
elif i18n has base tag:
    use base tag
else:
    use "en"
```

#### 10.9.4 Ограничение по channel_label

`channel_label` не локализуется автоматически по языку браузера.

Для multi-language event канал вводится вручную в формате:
`English name - abbreviation in original - original name`.

Для silent one-language multi-room event используется отдельная ручная логика (определяется перед мероприятием).

#### 10.9.5 Unicode и спецсимволы

Backend JSON и Listener UI обязаны поддерживать Unicode без потери символов (кириллица, иероглифы, диакритика и т.д.).

Emergency override details: см. docs/08_backend.md, раздел 9.14.



### 10.10. Active PLAY heartbeat control

Rules for MVP Stage IX:
- when listener has active PLAY state, web page sends heartbeat every `10 sec`;
- if backend does not receive heartbeat for `60 sec`, listener session must switch to reconnect-required state;
- heartbeat control is for active playback monitoring and room overflow protection.
- if session timeout happened while no active PLAY and user returns to the page/tab, web page must auto-reconnect backend WS (or auto page reload fallback).

Listener UX expectation:
- on reconnect-required state user sees reconnect flow without manual page reload where technically possible.

#### 10.10.1 Connection recovery rules (Listener)

Listener maintains `connectionState`:
- `CONNECTED`
- `STALE`
- `RECONNECTING`

`connectionState` becomes `STALE` when:
- heartbeat timeout;
- backend websocket disconnect;
- LiveKit disconnect;
- token expiry.

Reconnect triggers:
1) mandatory: channel button click;
2) optional: `document.visibilitychange` -> page becomes visible;
3) optional: network restored event.

On PLAY ACTION:
```
if connectionState == STALE:
    reconnect
    keep button active
    state = WAITING
else:
    ATTACH ACTION
```

Reconnect fallback:
```
if reconnect fails:
    reload page
```

Expected UX result:
- after STOP ACTION, return from background, idle on opened page, or other stale cases, user can press channel button once and receive audio again without extra manual recovery steps.

#### 10.10.2 Mobile system player behavior (Android/iOS)

Expected compatibility behavior:
- if user selected a channel button (PLAY state), page went background, and user pressed pause/play in system mobile player **before heartbeat timeout**, Listener must resume playback of the same last selected channel button;
- if timeout already happened and connection is `STALE`, system play action follows reconnect rules from 10.10.1.

#### 10.10.3 Backend availability banner texts (Listener web page)

Listener connection states and required texts:

- `CONNECTING` (`0-3s`):
  - `"Connecting..."`

- `RETRYING` (`3-10s`):
  - `"Trying to reconnect..."`

- `UNAVAILABLE` (`>10s`):
  - `"Unable to connect. Waiting for service..."`

Rule when backend connection restored:
- hide the backend-availability message immediately.

### 10.11. Future production features (no priority)

Следующие идеи считаются future/no-priority и в MVP не реализуются:
- backend-driven language selection по `ui_lang` от Listener;
- динамическая смена status texts во время мероприятия;
- серверная языковая персонализация текстов «на лету».
