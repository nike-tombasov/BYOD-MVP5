## 10. Listener Web UI (HTML)

WS wire-protocol canonical source: `docs/15_ws_schema_v1.md`.
This file describes Listener behavior/UX and must not conflict with canonical wire schema.

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
6) channel button не меняет цвет (не гаснет) сам за исключением перезапуска web page, перевода room status в CLOSED
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
- rapid-click race hardening is part of permanent listener baseline, because these races create non-deterministic state transitions.

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
* Listener does not receive or process any separate forced off-air command; it reacts only to regular room/channel state transitions.

### 10.8A. Canonical room_status behavior (permanent)

These rules are permanent listener canon (not stage-local):

- `BLOCKED`:
  - stop current sound immediately;
  - keep channel buttons clickable;
  - no sound is played while status is BLOCKED.

- `CLOSED`:
  - stop current sound immediately;
  - unpush current active button;
  - lock controls until status returns to OPENED;
  - no sound is played while status is CLOSED.

- Return to `OPENED` (both paths):
  - listener must continue working without page reload;
  - if button stayed active from BLOCKED path, sound resumes for that channel;
  - reconnect path is used only when backend marks session stale/reconnect-required.

Language/i18n rendering baseline (permanent):
- Listener auto-detects browser language with exact->base->`en` fallback.
- Backend sends full immutable `i18n_library` on connect/reconnect.
- Backend does not select language per listener.

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
4) Status texts после deploy считаются фиксированными и не меняются во время мероприятия.

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

Override details: см. docs/08_backend.md, раздел 9.14.

### 10.10. Active PLAY heartbeat control

Permanent baseline rules:
- after backend WS connect, backend waits `60 sec` for first ACTIVE PLAY trigger;
- Listener sends heartbeat every `10 sec` only when ACTIVE PLAY is running (`WAITING` / `PLAYING`);
- if backend does not receive heartbeat for `60 sec` during active PLAY, **backend** marks listener session as stale/reconnect-required;
- heartbeat control is for active playback monitoring and room overflow protection.
- Listener must NOT run its own local 60-second stale decision timer based on generic incoming WS silence.
- if session timeout happened while no active PLAY and user returns to the page/tab, recovery is allowed by reconnect triggers and UNAVAILABLE retry policy.

Listener UX expectation:
- on reconnect-required state user sees reconnect flow without manual page reload where technically possible.

#### 10.10.1 Connection recovery rules (Listener)

Listener maintains `connectionState`:
- `CONNECTED`
- `STALE`
- `RECONNECTING`

`connectionState` becomes `STALE` when:
- backend `reconnect_required` message (stale session);
- backend websocket disconnect;
- LiveKit disconnect;
- token expiry.

Reconnect triggers:
1) mandatory: channel button click;
2) optional: `document.visibilitychange` -> page becomes visible;
3) optional: network restored event.
4) automatic retry loop only while backend availability state is `UNAVAILABLE`.

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
    keep retry policy loop (no tight spam), optional reload fallback
```

Retry policy (canonical):
- while `RETRYING`: reconnect every `3 sec`;
- while `UNAVAILABLE`: reconnect every `10 sec`.

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

### 10.10. Local Wi-Fi mobile Listener media controls test

This manual test checks mobile system-player and locked-screen/background behavior on a local LAN. It is a compatibility experiment only; background or locked-screen playback remains browser/OS-dependent and is not guaranteed on all modern smartphones.

Operator setup:

- Put the laptop/server and phone on the same Wi-Fi/LAN.
- Find the laptop LAN IPv4 address, for example `192.168.1.50`.
- Configure Publisher to use backend WebSocket URL `ws://<LAN_IP>:8000/ws/publisher`.
- Open the Listener page from the phone through the LAN address served by the local static server, nginx, or dev server.
- If needed, add the Listener backend override: `?backend=ws://<LAN_IP>:8000/ws/listener`.
- Ensure backend/LiveKit config returns a phone-reachable LiveKit URL, for example `ws://<LAN_IP>:7880`.
- Allow the required backend, LiveKit, and web-server ports through the local firewall for the LAN test.
- HTTPS/WSS is not required for this local experiment unless the local setup already supports it.
- This test is only for mobile system player/background behavior, not for production security.

Manual checklist:

1. Start local backend.
2. Start local LiveKit.
3. Start local Listener static server/nginx/dev server.
4. Start Publisher on laptop.
5. Open Listener from phone over Wi-Fi.
6. Press a channel button.
7. Confirm audio plays.
8. Lock screen.
9. Observe whether audio continues.
10. Check whether lock-screen media controls appear.
11. Press pause from system player.
12. Unlock and verify Listener state is consistent.
13. Press play from system player if available.
14. Test switching channels after unlock.
15. Test STOP from page button after system pause/play.
16. Save phone model, OS version, browser, result, and logs.

Compatibility results template:

| Device | OS/version | Browser/version | Opened via HTTP LAN or HTTPS | Audio continues after lock: yes/no | System player appears: yes/no | System pause works: yes/no | System play works: yes/no | Playback stops unexpectedly after lock: yes/no | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

### 10.11. Manual iPhone Media Session soft-pause test

This test verifies that system media pause is a soft pause, not a full Listener STOP/detach. It improves Media Session behavior where the browser/OS supports it, but does not guarantee background or locked-screen playback on all iOS/Android browsers.

Device:

* iPhone 17e
* browser:
* iOS version:
* test date:

Steps:

1. Open Listener page.
2. Press one channel button.
3. Confirm audio plays.
4. Confirm iOS system player / Now Playing shows BYOD room name and channel name.
5. Press pause in iOS system player.
6. Expected after this PR:

   * BYOD should remain in system player if iOS allows it;
   * system player should not immediately switch to Yandex Music or another previous media app;
   * Listener page should retain selected channel state;
   * audio should be paused, not fully detached.
7. Press play in iOS system player.
8. Expected:

   * BYOD resumes the same selected channel if room is OPENED and track is available.
9. Unlock phone and inspect Listener page state.
10. Press current channel button on the page.
11. Expected:

* full STOP still works;
* it is acceptable if iOS then removes BYOD from system player because the user explicitly stopped the channel.

12. Repeat with screen locked.
13. Save diagnostics/log output if possible.

Acceptance criteria:

* Desktop Listener still works.
* Mobile Listener still starts only after channel button tap.
* One audio element remains.
* No per-channel `Audio()` objects are introduced.
* No subscribe-all behavior is introduced.
* Page STOP behavior remains compatible with current spec.
* System media pause is soft pause and does not detach/clear `srcObject`.
* System media play resumes the previously user-selected channel when possible.
