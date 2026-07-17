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
* console command protection model
* secret rotation policies

## 12.2 MVP domain-mode minimum security

1) Guest domain mode must use HTTPS/WSS only.
2) `/admin/*` must never be public.
3) `8000/tcp` must never be exposed publicly.
4) Listener token lifetime remains limited.
5) nginx must rate-limit `/ws/listener`.
6) nginx must rate-limit `/health`.
7) nginx must enforce request/body size limits.
8) Logs must not contain secrets.
9) The LiveKit API secret is generated per VPS/deploy and never stored in git.
10) Direct-IP test mode remains available, but IP URLs are not the primary guest QR links when domain mode is configured.
