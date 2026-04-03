## 6. Audio architecture

### 6.1. Audio pipeline проходит следующий путь (вариант):

audio device
↓
sounddevice
↓
audio capture
↓
audio queue
↓
LiveKit AudioFrame
↓
Opus codec
↓
WebRTC
↓
Browser

### 6.2. Требования к аудио

Принятые решения:
* Sample rate: 48000 Hz
* Channels: stereo
* Frame size: 960 samples
* Codec: Opus

Причины:
* стандарт WebRTC
* отсутствие resampling
* стабильная работа устройств

### 6.3. Ограничения на sample rate

В системе допускается только 48000 Hz.
Если устройство работает на другом sample rate, возможна ошибка.

Publisher должен отображать status:
"Device error. Check system samplerate (48000 Hz only)"

### 6.4. Always-open device

Sounddevice может быть открыт заранее,
но enqueue аудио начинается только после получения owner.

device open
↓
capture
↓
send only when ON AIR

Причина:
минимальная задержка,
стабильность

### 6.5. Задержка звука

Целевая задержка между входящим audio device и web page - 150-300 ms. Максимум 500 ms.

Планируемые методы снижения задержки:
* smaller buffers
* opus tuning
* faster queues