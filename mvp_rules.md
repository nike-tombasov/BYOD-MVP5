# MVP rules for current stage

Goal: working multi-publisher audio engine

Do NOT implement:

- advanced UI design
- admin web UI
- channel recording
- statistics
- security features
- authentication for listeners
- token expiration logic
- dynamic PIN generation
- multi-room support
- advanced logging
- deployment automation

Use fixed values for MVP:

- PIN = 123456
- room_name = test room
- channels = floor, rus, eng
- room_status = OPENED always
- JWT lifetime = 5h

Scope:

- max 3 channels required for MVP test
- scaling to 32 channels only after logic proven
- minimal UI (functional only)
- console logging allowed
- no performance optimization yet

Rules:

- sound must work after each step
- no breaking working functionality
- implement minimal viable logic
- avoid abstractions















1. замена текстового анализатора звука в Publisher UI на VU meter, RMS meter, audio level bars
2. цвета всех статусов в Publisher UI 
3. реализовать процедуру статуса connecting... в Publisher UI
4. тестировать более 3х каналов 
5. использовать статусы комнат closed и blocked, пока всегда OPENED
6. ручной PIN - пока использовать 123456
7. аудиозапись
8. web admin 
9. ввод начальных данных по комнате (использовать test room, floor, rus, English)
10. выдавать токен сроком меньше 5 часов
11. если использовать WebSocket, то не разделять state для Publisher и Listener - рассылать одно и то же для упрощения тестирований