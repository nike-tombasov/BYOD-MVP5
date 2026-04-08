## 7. LiveKit SFU Engine

### 7.1. Версия и документация

На всей структуре проекта строгое соблюдение фокуса на LiveKit v1.9.11 (либо вескоаргументированно другой стабильной версии, при необходимости)

Pinned compatibility matrix (MVP baseline):
* LiveKit Server: `1.9.11`
* Python SDK: `livekit==1.1.5`
* Python API SDK: `livekit-api==1.1.0`
* livekit protocol package: `livekit-protocol==1.1.3` (transitive environment pin)
* Listener JS SDK: `1.15.13`
  * local pinned artifact: `src/listener/vendor/livekit-client.umd.1.15.13.js`
  * CDN source: `https://unpkg.com/livekit-client@1.15.13/dist/livekit-client.umd.js`

Patch policy:
* LiveKit Server `1.9.12+` допустим только после compatibility checklist и явного обновления pin в документации.

Любое изменение любой версии из матрицы допустимо только после отдельного compatibility review и обновления hard rules / roadmap / open issues resolution note.

Официальная документацая, обязательная к соблюдению:
* https://github.com/livekit/livekit 
* https://docs.livekit.io/intro/overview/

### 7.2. Функции:

* connect room
* publishes tracks — выполняется только после разрешения backend (owner == self)
* enqueue audio
* send frames
* statistics

### 7.3. Асинхронный движок

LiveKit работает в отдельном event loop.

thread
↓
async loop

Это необходимо из-за Qt UI.

### 7.4. Особенность на Ubuntu

Учесть при разворачивании LiveKit на VPS строку про use external IP. 
Опущение это вводной приводит к неработоспособности LiveKit.
