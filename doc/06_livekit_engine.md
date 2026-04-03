## 7. LiveKit SFU Engine

### 7.1. Версия и документация

На всей структуре проекта строгое соблюдение фокуса на LiveKit v1.9.11 (либо вескоаргументированно другой стабильной версии, при необходимости)

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