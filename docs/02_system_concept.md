## 2. Main system concept

Архитектура системы построена на модели:

Publisher (Windows app)
        ↓
Backend (token + room management)
        ↓
LiveKit Server (SFU)
        ↓
Browser listeners

Где:
* Publisher - Приложение для room technician, которое publishes LiveKit audio\track.
* Backend - server for room management, PIN, token and channel configuration.
* LiveKit - SFU WebRTC server, which distributes audio channels to listeners.
* Listener - web page (landing), where users connect and choose audio channels to listen target sound using their own devices.
