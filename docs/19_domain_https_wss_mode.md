## 19. Domain HTTPS/WSS mode

This document records the MVP domain-mode deployment model. Domain mode is optional for Stage XII; the existing direct-IP pilot test mode remains available for VPS pilots and fallback diagnostics.

### 19.1 Subdomain roles

- `listen-*` subdomains are guest-facing Listener entry points. They serve the same Listener HTML and WebSocket path under HTTPS/WSS for QR links.
- `lk-*` or `livekit-*` subdomains are LiveKit signaling / WebRTC entry endpoints used by the LiveKit SDK.
- `admin-*` is reserved for a future Admin UI. Stage XII does not implement that UI; the reserved HTTPS host returns `404` and never proxies the backend `/admin/*` API.
- The backend remains a private service behind nginx. Public guest traffic must not expose backend port `8000/tcp` directly.

The Publisher UI has no domain. Its operator continues to enter a backend URL manually, for example `ws://194.58.118.140/ws/publisher` through nginx. Do not create Publisher DNS records.

### 19.2 DNS A-record model

Each active VPS receives a Listener and LiveKit A-record pair that points to that VPS public IPv4 address. The same VPS may optionally receive a reserved `admin-*` A-record for a future Admin UI:

```text
listen-1.k-pls.ru -> 194.58.118.140
lk-1.k-pls.ru     -> 194.58.118.140
admin-1.k-pls.ru  -> 194.58.118.140  # reserved future Admin UI; no backend /admin/* proxy
```

Stage XII does not implement the Admin UI, and `admin-*` must never proxy the backend `/admin/*` API. The Publisher continues to have no DNS record.

For MVP operations, one simultaneous hall/event equals one VPS. A second simultaneous hall/event uses a second VPS and a second subdomain pair.

### 19.3 Event aliases are URL paths, not DNS rooms

Event aliases are path aliases on the same Listener HTML, for example `/event/main-hall` or `/event/workshop-a`. They do not create separate DNS records, separate LiveKit rooms, or separate simultaneous halls by themselves.

This keeps guest QR links readable while preserving the MVP capacity rule: one simultaneous hall/event is served by one VPS.

### 19.4 Direct-IP pilot mode

Direct-IP pilot mode remains supported for practical testing, diagnostics, and emergency fallback. In domain mode, domain URLs are the primary guest URLs, while direct-IP HTTP/WS remains available on the same VPS for diagnostics and operator fallback. Direct-IP fallback does not provide HTTPS/WSS. Domain HTTPS/WSS mode is not mandatory for every pilot.

Set `BYOD_DOMAIN_TLS_MODE=true` to opt in. Deployment then validates the HTTPS/WSS origins, verifies every configured A-record against the VPS IPv4, obtains a Let's Encrypt certificate, and installs the domain nginx configuration. With the default `false`, no domain values or certificate are required and existing HTTP/WS behavior remains in use.
