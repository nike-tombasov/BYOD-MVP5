## 12. Защита, безопасность, кибербезопасность (в будущем):

* Поведения системы при обрывах интернета для сохранения стабильности
* Ограничить по времени выдачу JWT token Identity listener на 1 IP 
* Возможные меры по защите от ddos и т.п.
* Генеративная смена JWT token secret key синхронно  у LiveKit Server и backend при разворачивании VPS (deploy)
* Управляемая генерация PIN при разворачивании сервера (через  Admin web UI)
* Ограничения по лимиту токенов и их сроку - проработать логику, чтобы не накрылось мероприятие
* Rate-limit (Nginx / FastAPI / Flask middleware)
* Cloudflare только для сайта (не для WebRTC!)

## 12.1 Post-first-VPS-test security backlog

* WS message ACK security
* dedupe replay protection
* token abuse protection
* IP rate limiting hardening
* audit logging for emergency override commands
* console command protection model
* secret rotation policies
